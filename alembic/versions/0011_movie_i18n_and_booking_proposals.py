from alembic import op
import sqlalchemy as sa

revision = "0011_movie_i18n_booking_proposals"
down_revision = "0010_user_telegram_id_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("title_ru", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("title_uz", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("genre_ru", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("genre_uz", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("description_ru", sa.Text(), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("description_uz", sa.Text(), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("country_ru", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("country_uz", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("director_ru", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("director_uz", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("cast_json_ru", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("movies", sa.Column("cast_json_uz", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("bookings", sa.Column("proposed_session", sa.String(length=30), nullable=False, server_default=""))
    op.add_column("bookings", sa.Column("admin_note", sa.Text(), nullable=False, server_default=""))

    op.execute(
        """
        UPDATE movies
        SET title_ru = title,
            title_uz = title,
            genre_ru = genre,
            genre_uz = genre,
            description_ru = description,
            description_uz = description,
            country_ru = country,
            country_uz = country,
            director_ru = director,
            director_uz = director,
            cast_json_ru = cast_json,
            cast_json_uz = cast_json
        """
    )


def downgrade() -> None:
    op.drop_column("bookings", "admin_note")
    op.drop_column("bookings", "proposed_session")
    op.drop_column("movies", "cast_json_uz")
    op.drop_column("movies", "cast_json_ru")
    op.drop_column("movies", "director_uz")
    op.drop_column("movies", "director_ru")
    op.drop_column("movies", "country_uz")
    op.drop_column("movies", "country_ru")
    op.drop_column("movies", "description_uz")
    op.drop_column("movies", "description_ru")
    op.drop_column("movies", "genre_uz")
    op.drop_column("movies", "genre_ru")
    op.drop_column("movies", "title_uz")
    op.drop_column("movies", "title_ru")
