"""Stage 3: admin-managed settings, unified `shows` schedule, content tables.

Data is preserved: `session_prices` rows and every time in `movies.sessions_json`
are expanded into `shows` before the old structures are dropped.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import sqlalchemy as sa
from alembic import op

revision = "0012_settings_shows_content"
down_revision = "0011_movie_i18n_booking_proposals"
branch_labels = None
depends_on = None

#: How far ahead the old "any time, any day" schedule is materialised.
EXPAND_DAYS = 14

SETTINGS_COLUMNS = [
    ("name", sa.String(160), "Nova Cinema"),
    ("name_uz", sa.String(160), "Nova Cinema"),
    ("address", sa.String(255), "Юксалиш 97А"),
    ("address_uz", sa.String(255), "Yuksalish 97A"),
    ("phone", sa.String(32), "+998 91 326 20 65"),
    ("telegram_url", sa.String(255), "https://t.me/novasinema"),
    ("instagram_url", sa.String(255), "https://www.instagram.com/nova_cinema__"),
    ("map_url", sa.String(512), ""),
    ("work_hours", sa.String(120), "10:00 - 23:00"),
    ("work_hours_uz", sa.String(120), "10:00 - 23:00"),
    ("about", sa.Text(), ""),
    ("about_uz", sa.Text(), ""),
    ("currency", sa.String(8), "UZS"),
]

SETTINGS_INT_COLUMNS = [
    ("hall_rows", 3),
    ("hall_cols", 5),
    ("max_seats_per_booking", 4),
    ("hold_minutes", 10),
    ("booking_days_ahead", 7),
]



def _add_timestamp_column(table: str, name: str) -> None:
    """Add a NOT NULL timestamp column on both PostgreSQL and SQLite.

    SQLite rejects `ADD COLUMN ... DEFAULT CURRENT_TIMESTAMP` ("non-constant
    default"), so the column is added nullable, backfilled, then tightened.
    """
    op.add_column(table, sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text(f"UPDATE {table} SET {name} = :now").bindparams(now=datetime.now(timezone.utc)))
    with op.batch_alter_table(table) as batch:
        batch.alter_column(name, existing_type=sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    bind = op.get_bind()

    # --- cinema_settings -----------------------------------------------------
    for name, column_type, default in SETTINGS_COLUMNS:
        op.add_column(
            "cinema_settings",
            sa.Column(name, column_type, nullable=False, server_default=default),
        )
    for name, default in SETTINGS_INT_COLUMNS:
        op.add_column(
            "cinema_settings",
            sa.Column(name, sa.Integer(), nullable=False, server_default=str(default)),
        )
    op.add_column("cinema_settings", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("cinema_settings", sa.Column("longitude", sa.Float(), nullable=True))
    _add_timestamp_column("cinema_settings", "updated_at")
    if bind.execute(sa.text("SELECT COUNT(*) FROM cinema_settings")).scalar() == 0:
        bind.execute(
            sa.text("INSERT INTO cinema_settings (id, base_ticket_price) VALUES (1, 30000)")
        )

    # --- shows ---------------------------------------------------------------
    op.create_table(
        "shows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id"), nullable=False),
        sa.Column("show_date", sa.String(10), nullable=False),
        sa.Column("start_time", sa.String(5), nullable=False),
        sa.Column("ticket_price", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("movie_id", "show_date", "start_time", name="uq_show_slot"),
    )
    op.create_index("ix_shows_movie_id", "shows", ["movie_id"])
    op.create_index("ix_shows_show_date", "shows", ["show_date"])
    op.create_index("ix_shows_start_time", "shows", ["start_time"])
    op.create_index("ix_shows_status", "shows", ["status"])

    seen: set[tuple[int, str, str]] = set()
    insert_show = sa.text(
        "INSERT INTO shows (movie_id, show_date, start_time, ticket_price, status)"
        " VALUES (:movie_id, :show_date, :start_time, :ticket_price, :status)"
    )

    # 1:1 from the per-date overrides.
    for row in bind.execute(
        sa.text("SELECT movie_id, show_date, session, ticket_price, status FROM session_prices")
    ):
        start_time = str(row.session)[:5]
        key = (row.movie_id, row.show_date, start_time)
        if key in seen:
            continue
        seen.add(key)
        bind.execute(
            insert_show,
            {
                "movie_id": row.movie_id,
                "show_date": row.show_date,
                "start_time": start_time,
                "ticket_price": row.ticket_price,
                "status": row.status or "active",
            },
        )

    # Expand the base schedule, which had times but no dates.
    today = date.today()
    window = [(today + timedelta(days=offset)).isoformat() for offset in range(EXPAND_DAYS)]
    for row in bind.execute(sa.text("SELECT id, sessions_json FROM movies")):
        try:
            times = json.loads(row.sessions_json or "[]")
        except (TypeError, ValueError):
            times = []
        for start_time in {str(value)[:5] for value in times if value}:
            for show_date in window:
                key = (row.id, show_date, start_time)
                if key in seen:
                    continue
                seen.add(key)
                bind.execute(
                    insert_show,
                    {
                        "movie_id": row.id,
                        "show_date": show_date,
                        "start_time": start_time,
                        "ticket_price": None,
                        "status": "active",
                    },
                )

    op.drop_table("session_prices")

    # --- movies --------------------------------------------------------------
    op.add_column("movies", sa.Column("is_new", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("movies", sa.Column("new_until", sa.String(10), nullable=False, server_default=""))
    op.create_index("ix_movies_is_new", "movies", ["is_new"])
    with op.batch_alter_table("movies") as batch:
        batch.drop_column("sessions_json")

    # --- bookings ------------------------------------------------------------
    op.add_column("bookings", sa.Column("ticket_price", sa.Integer(), nullable=False, server_default="0"))
    _add_timestamp_column("bookings", "created_at")
    op.create_index("ix_bookings_created_at", "bookings", ["created_at"])
    # Backfill the frozen unit price from what was actually charged.
    bind.execute(
        sa.text(
            "UPDATE bookings SET ticket_price = CASE"
            " WHEN seats IS NULL OR seats = '' THEN 0"
            " ELSE total / (LENGTH(seats) - LENGTH(REPLACE(seats, ',', '')) + 1)"
            " END"
        )
    )
    bind.execute(sa.text("UPDATE bookings SET status = 'watched' WHERE status = 'completed'"))

    # --- content tables ------------------------------------------------------
    op.create_table(
        "bonuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False, server_default=""),
        sa.Column("title_uz", sa.String(160), nullable=False, server_default=""),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("text_uz", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )
    op.create_index("ix_bonuses_is_active", "bonuses", ["is_active"])
    op.create_index("ix_bonuses_sort_order", "bonuses", ["sort_order"])

    op.create_table(
        "melodies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False, server_default=""),
        sa.Column("file_url", sa.String(512), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )
    op.create_index("ix_melodies_sort_order", "melodies", ["sort_order"])

    op.create_table(
        "gallery_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("image_url", sa.String(512), nullable=False),
        sa.Column("caption", sa.String(255), nullable=False, server_default=""),
        sa.Column("caption_uz", sa.String(255), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )
    op.create_index("ix_gallery_images_sort_order", "gallery_images", ["sort_order"])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("gallery_images")
    op.drop_table("melodies")
    op.drop_table("bonuses")

    bind.execute(sa.text("UPDATE bookings SET status = 'completed' WHERE status = 'watched'"))
    bind.execute(sa.text("UPDATE bookings SET status = 'pending' WHERE status = 'contacting'"))
    op.drop_index("ix_bookings_created_at", table_name="bookings")
    with op.batch_alter_table("bookings") as batch:
        batch.drop_column("created_at")
        batch.drop_column("ticket_price")

    op.add_column("movies", sa.Column("sessions_json", sa.Text(), nullable=False, server_default="[]"))
    op.drop_index("ix_movies_is_new", table_name="movies")
    with op.batch_alter_table("movies") as batch:
        batch.drop_column("new_until")
        batch.drop_column("is_new")

    op.create_table(
        "session_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id"), nullable=False),
        sa.Column("show_date", sa.String(10), nullable=False),
        sa.Column("session", sa.String(30), nullable=False),
        sa.Column("ticket_price", sa.Integer(), nullable=True),
        sa.Column("seats_count", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.UniqueConstraint("movie_id", "show_date", "session", name="uq_session_price"),
    )
    bind.execute(
        sa.text(
            "INSERT INTO session_prices (movie_id, show_date, session, ticket_price, status)"
            " SELECT movie_id, show_date, start_time, ticket_price, status FROM shows"
        )
    )
    op.drop_table("shows")

    for name in ("updated_at", "longitude", "latitude"):
        op.drop_column("cinema_settings", name)
    for name, _ in SETTINGS_INT_COLUMNS:
        op.drop_column("cinema_settings", name)
    for name, _, _ in SETTINGS_COLUMNS:
        op.drop_column("cinema_settings", name)
