"""Widen users.telegram_id to BIGINT.

SQLite has no ALTER COLUMN TYPE and stores integers dynamically (up to 8 bytes),
so the column is already wide enough there.  Guarding on the dialect keeps the
chain runnable on the local SQLite database used for development and tests.
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_user_telegram_id_bigint"
down_revision = "0009_booking_username"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        postgresql_using="telegram_id::bigint",
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="telegram_id::integer",
    )
