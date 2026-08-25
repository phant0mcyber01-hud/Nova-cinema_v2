"""Phase A: booking the hall instead of a film.

The mini app no longer reserves a screening.  It reserves a number of places in
the one auditorium at a date and one of the administrator's fixed times, and the
film is agreed with the administrator afterwards.  Three things follow:

* `slot_templates` -- the fixed times, owned by the cinema and attached to no
  movie.  Seeded with 12:00, 14:00, 16:00, 18:00 and 20:00.
* `capacity_holds` -- short-lived claims on the hall's virtual capacity tokens,
  keyed by date and time *only*.  That unique key is what physically refuses to
  sell the thirteenth place, and dropping `movie_id` out of it is the whole
  point: the same twelve chairs cannot be sold twice because two viewers
  happened to agree different films for the same hour.
* `bookings.party_size`, and a nullable `bookings.movie_id`.

Nothing is destroyed.  `seats` keeps its shape, every historical request keeps
its film, its code, its uuid and its QR token, and `party_size` is backfilled
from the seat list so old and new rows count against the hall the same way.
The movie-bound `shows` schedule is left in place for the legacy endpoints.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_generic_capacity_booking"
down_revision = "0017_booking_promo_code"
branch_labels = None
depends_on = None

#: The times the cinema opens. Admin-managed from here on; this only seeds them.
DEFAULT_SLOT_TIMES = ("12:00", "14:00", "16:00", "18:00", "20:00")
DEFAULT_ADMIN_PHONE = "91 326 20 65"
DEFAULT_ADMIN_TELEGRAM = "@Hhkcjoj"

#: Number of comma-separated entries in `seats`, in SQL both SQLite and
#: PostgreSQL understand. An empty seat list means nobody, not one person.
_SEAT_COUNT = (
    "CASE WHEN seats IS NULL OR seats = '' THEN 0"
    " ELSE LENGTH(seats) - LENGTH(REPLACE(seats, ',', '')) + 1 END"
)


def upgrade() -> None:
    op.create_table(
        "slot_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        # Reserved for a later per-slot price. The current formula is
        # `base_ticket_price * party_size` and deliberately ignores it.
        sa.Column("ticket_price", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_slot_templates_start_time", "slot_templates", ["start_time"], unique=True)
    op.create_index("ix_slot_templates_is_active", "slot_templates", ["is_active"])
    op.create_index("ix_slot_templates_sort_order", "slot_templates", ["sort_order"])

    slot_templates = sa.table(
        "slot_templates",
        sa.column("start_time", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        slot_templates,
        [
            {"start_time": start_time, "is_active": True, "sort_order": order}
            for order, start_time in enumerate(DEFAULT_SLOT_TIMES)
        ],
    )

    op.create_table(
        "capacity_holds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("show_date", sa.String(length=10), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("token", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        # No `movie_id`: the hall is the resource, and the film is not.
        sa.UniqueConstraint("show_date", "start_time", "token", name="uq_capacity_hold"),
    )
    op.create_index("ix_capacity_holds_show_date", "capacity_holds", ["show_date"])
    op.create_index("ix_capacity_holds_start_time", "capacity_holds", ["start_time"])
    op.create_index("ix_capacity_holds_user_id", "capacity_holds", ["user_id"])
    op.create_index("ix_capacity_holds_expires_at", "capacity_holds", ["expires_at"])

    op.add_column(
        "bookings", sa.Column("party_size", sa.Integer(), nullable=False, server_default="0")
    )
    # Old requests already say how many people are coming -- it is the length of
    # the seat list. Backfilling it means one rule counts the hall for every row.
    op.execute(sa.text(f"UPDATE bookings SET party_size = {_SEAT_COUNT}"))

    with op.batch_alter_table("bookings") as batch:
        # A request no longer needs a film. `seats` is deliberately left exactly
        # as it was: legacy rows keep their real seat labels, and generic ones
        # store the internal capacity tokens in the same column.
        batch.alter_column("movie_id", existing_type=sa.Integer(), nullable=True)

    op.add_column(
        "cinema_settings",
        sa.Column(
            "admin_phone",
            sa.String(length=32),
            nullable=False,
            server_default=DEFAULT_ADMIN_PHONE,
        ),
    )
    op.add_column(
        "cinema_settings",
        sa.Column(
            "admin_telegram",
            sa.String(length=64),
            nullable=False,
            server_default=DEFAULT_ADMIN_TELEGRAM,
        ),
    )

    # Seat holds live for minutes and are meaningless after a deployment. Left
    # behind they would keep places blocked in a hall that now counts them
    # globally, so the ephemeral table starts empty. No booking is touched.
    op.execute(sa.text("DELETE FROM seat_holds"))


def downgrade() -> None:
    bind = op.get_bind()
    orphans = bind.execute(sa.text("SELECT COUNT(*) FROM bookings WHERE movie_id IS NULL")).scalar()
    if orphans:
        # `movie_id` becomes mandatory again, and these requests never had one.
        # Deleting them would throw away real bookings, so they adopt the oldest
        # film in the catalog instead: the row survives with the wrong title
        # rather than not surviving at all. An empty catalog leaves no honest
        # option, so the rollback stops rather than destroying anything.
        fallback = bind.execute(sa.text("SELECT MIN(id) FROM movies")).scalar()
        if fallback is None:
            raise RuntimeError(
                f"{orphans} booking(s) have no film and the catalog is empty, so movie_id "
                "cannot be made NOT NULL again without losing them. Add a placeholder movie "
                "and retry the downgrade."
            )
        bind.execute(
            sa.text("UPDATE bookings SET movie_id = :movie_id WHERE movie_id IS NULL"),
            {"movie_id": fallback},
        )

    with op.batch_alter_table("bookings") as batch:
        batch.alter_column("movie_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("party_size")

    with op.batch_alter_table("cinema_settings") as batch:
        batch.drop_column("admin_telegram")
        batch.drop_column("admin_phone")

    op.drop_index("ix_capacity_holds_expires_at", table_name="capacity_holds")
    op.drop_index("ix_capacity_holds_user_id", table_name="capacity_holds")
    op.drop_index("ix_capacity_holds_start_time", table_name="capacity_holds")
    op.drop_index("ix_capacity_holds_show_date", table_name="capacity_holds")
    op.drop_table("capacity_holds")

    op.drop_index("ix_slot_templates_sort_order", table_name="slot_templates")
    op.drop_index("ix_slot_templates_is_active", table_name="slot_templates")
    op.drop_index("ix_slot_templates_start_time", table_name="slot_templates")
    op.drop_table("slot_templates")
