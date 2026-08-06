"""admin notification read state"""
from alembic import op
import sqlalchemy as sa

revision = "0005_notification_read"
down_revision = "0004_status_price"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("admin_notifications", sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade() -> None:
    op.drop_column("admin_notifications", "is_read")
