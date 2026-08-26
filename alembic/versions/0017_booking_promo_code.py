"""Add the promo code a viewer passes to the admin with a booking request."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_booking_promo_code"
down_revision = "0016_movie_hits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("promo_code", sa.String(length=64), nullable=False, server_default=""),
    )


def downgrade() -> None:
    with op.batch_alter_table("bookings") as batch:
        batch.drop_column("promo_code")
