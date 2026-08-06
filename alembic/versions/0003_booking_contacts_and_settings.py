"""booking contacts, configurable price and admin notifications"""
from alembic import op
import sqlalchemy as sa

revision = "0003_contacts_settings"
down_revision = "0002_booking_holds"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("bookings", sa.Column("first_name", sa.String(80), nullable=False, server_default=""))
    op.add_column("bookings", sa.Column("last_name", sa.String(80), nullable=False, server_default=""))
    op.add_column("bookings", sa.Column("phone", sa.String(32), nullable=False, server_default=""))
    op.add_column("bookings", sa.Column("comment", sa.Text(), nullable=False, server_default=""))
    op.create_table("cinema_settings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("base_ticket_price", sa.Integer(), nullable=False))
    op.execute("INSERT INTO cinema_settings (id, base_ticket_price) VALUES (1, 30000)")
    op.create_table("admin_notifications", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))

def downgrade() -> None:
    op.drop_table("admin_notifications"); op.drop_table("cinema_settings"); op.drop_column("bookings", "comment"); op.drop_column("bookings", "phone"); op.drop_column("bookings", "last_name"); op.drop_column("bookings", "first_name")
