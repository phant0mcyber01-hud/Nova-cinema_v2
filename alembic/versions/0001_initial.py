"""initial async SQLAlchemy schema"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("telegram_id", sa.Integer(), nullable=False, unique=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("role", sa.String(20), nullable=False))
    op.create_table("movies", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(255), nullable=False), sa.Column("genre", sa.String(120), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("poster", sa.String(1024), nullable=False), sa.Column("trailer_id", sa.String(64), nullable=False), sa.Column("duration", sa.Integer(), nullable=False), sa.Column("age", sa.Integer(), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("country", sa.String(255), nullable=False), sa.Column("director", sa.String(255), nullable=False), sa.Column("cast_json", sa.Text(), nullable=False), sa.Column("gallery_json", sa.Text(), nullable=False), sa.Column("imdb", sa.Float(), nullable=False), sa.Column("kinopoisk", sa.Float(), nullable=False), sa.Column("sessions_json", sa.Text(), nullable=False))
    op.create_table("bookings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id"), nullable=False), sa.Column("session", sa.String(30), nullable=False), sa.Column("seats", sa.String(255), nullable=False), sa.Column("status", sa.String(20), nullable=False))
    op.create_table("reviews", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id"), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("rating", sa.Integer(), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("approved", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))

def downgrade() -> None:
    op.drop_table("reviews"); op.drop_table("bookings"); op.drop_table("movies"); op.drop_table("users")
