"""booking status lifecycle and price priority"""
from alembic import op
import sqlalchemy as sa

revision = "0004_status_price"
down_revision = "0003_contacts_settings"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("movies", sa.Column("ticket_price", sa.Integer(), nullable=True))
    op.create_table("session_prices", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id"), nullable=False), sa.Column("show_date", sa.String(10), nullable=False), sa.Column("session", sa.String(30), nullable=False), sa.Column("ticket_price", sa.Integer(), nullable=True), sa.UniqueConstraint("movie_id", "show_date", "session", name="uq_session_price"))
    op.execute("UPDATE bookings SET status = 'confirmed' WHERE status NOT IN ('pending', 'confirmed', 'cancelled', 'completed')")

def downgrade() -> None:
    op.drop_table("session_prices"); op.drop_column("movies", "ticket_price")
