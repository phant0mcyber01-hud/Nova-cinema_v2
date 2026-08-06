"""production query indexes"""
from alembic import op

revision = "0008_production_indexes"
down_revision = "0007_admin_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_movies_title", "movies", ["title"])
    op.create_index("ix_movies_genre", "movies", ["genre"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_reviews_movie_id", "reviews", ["movie_id"])
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"])
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])
    op.create_index("ix_bookings_movie_id", "bookings", ["movie_id"])
    op.create_index("ix_bookings_show_date", "bookings", ["show_date"])
    op.create_index("ix_bookings_status", "bookings", ["status"])
    op.create_index("ix_user_notifications_user_id", "user_notifications", ["user_id"])
    op.create_index("ix_user_notifications_is_read", "user_notifications", ["is_read"])
    op.create_index("ix_admin_notifications_booking_id", "admin_notifications", ["booking_id"])
    op.create_index("ix_admin_notifications_is_read", "admin_notifications", ["is_read"])
    op.create_index("ix_session_prices_show_date", "session_prices", ["show_date"])
    op.create_index("ix_seat_holds_user_id", "seat_holds", ["user_id"])
    op.create_index("ix_seat_holds_expires_at", "seat_holds", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_seat_holds_expires_at", table_name="seat_holds")
    op.drop_index("ix_seat_holds_user_id", table_name="seat_holds")
    op.drop_index("ix_session_prices_show_date", table_name="session_prices")
    op.drop_index("ix_admin_notifications_is_read", table_name="admin_notifications")
    op.drop_index("ix_admin_notifications_booking_id", table_name="admin_notifications")
    op.drop_index("ix_user_notifications_is_read", table_name="user_notifications")
    op.drop_index("ix_user_notifications_user_id", table_name="user_notifications")
    op.drop_index("ix_bookings_status", table_name="bookings")
    op.drop_index("ix_bookings_show_date", table_name="bookings")
    op.drop_index("ix_bookings_movie_id", table_name="bookings")
    op.drop_index("ix_bookings_user_id", table_name="bookings")
    op.drop_index("ix_reviews_user_id", table_name="reviews")
    op.drop_index("ix_reviews_movie_id", table_name="reviews")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_movies_genre", table_name="movies")
    op.drop_index("ix_movies_title", table_name="movies")
