"""Prevent stale booking lifecycle writers from overwriting each other."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_booking_optimistic_lock"
down_revision = "0021_settings_important_and_faq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    with op.batch_alter_table("bookings") as batch:
        batch.drop_column("version")
