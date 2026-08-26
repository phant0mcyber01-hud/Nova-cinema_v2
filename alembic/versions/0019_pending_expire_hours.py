"""A request the administrator never answered stops holding the hall.

Payment is manual, so a request waits in `pending` until somebody calls the
viewer back. Nothing released those places, which meant one forgotten request
kept part of a twelve-seat hall out of circulation permanently.

`pending_expire_hours` is how long a request may wait. The default is 24 hours;
0 switches the timer off for a cinema that would rather chase every request by
hand. Nothing is deleted and no existing request is touched by this migration --
it only adds the setting.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_pending_expire_hours"
down_revision = "0018_generic_capacity_booking"
branch_labels = None
depends_on = None

DEFAULT_PENDING_EXPIRE_HOURS = "24"


def upgrade() -> None:
    op.add_column(
        "cinema_settings",
        sa.Column(
            "pending_expire_hours",
            sa.Integer(),
            nullable=False,
            server_default=DEFAULT_PENDING_EXPIRE_HOURS,
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("cinema_settings") as batch:
        batch.drop_column("pending_expire_hours")
