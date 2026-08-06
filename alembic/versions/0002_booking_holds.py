"""booking holds and confirmation fields"""
from alembic import op
import sqlalchemy as sa

revision = "0002_booking_holds"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("bookings", sa.Column("show_date", sa.String(10), nullable=False, server_default=""))
    op.add_column("bookings", sa.Column("code", sa.String(32), nullable=False, server_default=""))
    op.add_column("bookings", sa.Column("total", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("seat_holds", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id"), nullable=False), sa.Column("show_date", sa.String(10), nullable=False), sa.Column("session", sa.String(30), nullable=False), sa.Column("seat", sa.String(10), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("movie_id", "show_date", "session", "seat", name="uq_seat_hold"))

def downgrade() -> None:
    op.drop_table("seat_holds"); op.drop_column("bookings", "total"); op.drop_column("bookings", "code"); op.drop_column("bookings", "show_date")
