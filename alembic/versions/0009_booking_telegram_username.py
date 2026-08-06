"""booking telegram username contact"""
from alembic import op
import sqlalchemy as sa

revision = "0009_booking_username"
down_revision = "0008_production_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("telegram_username", sa.String(80), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("bookings", "telegram_username")
