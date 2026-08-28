"""Allow viewers to clear terminal history without deleting booking audit rows."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_viewer_history_retention"
down_revision = "0022_booking_optimistic_lock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("viewer_hidden_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_bookings_viewer_hidden_at", "bookings", ["viewer_hidden_at"])


def downgrade() -> None:
    op.drop_index("ix_bookings_viewer_hidden_at", table_name="bookings")
    with op.batch_alter_table("bookings") as batch:
        batch.drop_column("viewer_hidden_at")