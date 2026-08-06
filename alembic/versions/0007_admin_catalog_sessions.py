"""admin catalog and session management fields"""
from alembic import op
import sqlalchemy as sa

revision = "0007_admin_catalog"
down_revision = "0006_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(80), nullable=False, server_default=""))
    op.add_column("movies", sa.Column("internal_rating", sa.Float(), nullable=True))
    op.add_column("movies", sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("movies", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("session_prices", sa.Column("seats_count", sa.Integer(), nullable=False, server_default="80"))
    op.add_column("session_prices", sa.Column("status", sa.String(20), nullable=False, server_default="active"))
    op.create_index("ix_movies_is_published", "movies", ["is_published"])
    op.create_index("ix_movies_sort_order", "movies", ["sort_order"])
    op.create_index("ix_session_prices_status", "session_prices", ["status"])


def downgrade() -> None:
    op.drop_index("ix_session_prices_status", table_name="session_prices")
    op.drop_index("ix_movies_sort_order", table_name="movies")
    op.drop_index("ix_movies_is_published", table_name="movies")
    op.drop_column("session_prices", "status")
    op.drop_column("session_prices", "seats_count")
    op.drop_column("movies", "sort_order")
    op.drop_column("movies", "is_published")
    op.drop_column("movies", "internal_rating")
    op.drop_column("users", "username")
