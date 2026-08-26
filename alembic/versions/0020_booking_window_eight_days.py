"""The booking window becomes today plus 7 more days -- 8 dates, not 7.

The client's own example: today is Wed 25 Aug, the furthest bookable day is
1 Sep. Counted out that is 8 calendar dates (25, 26, 27, 28, 29, 30, 31, 1),
so "today" is one of the seven days ahead, not an extra day on top of them.

This only touches the *default* a fresh cinema starts with. If the
administrator already changed `booking_days_ahead` away from the old default
of 7 through the settings screen, that is a deliberate choice and stays
untouched -- the data migration below only nudges rows still sitting on the
old default, exactly as an administrator seeing "still 7" would expect.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_booking_window_eight_days"
down_revision = "0019_pending_expire_hours"
branch_labels = None
depends_on = None

OLD_DEFAULT = 7
NEW_DEFAULT = 8


def upgrade() -> None:
    with op.batch_alter_table("cinema_settings") as batch:
        batch.alter_column(
            "booking_days_ahead",
            existing_type=sa.Integer(),
            server_default=str(NEW_DEFAULT),
        )
    op.execute(
        sa.text(
            "UPDATE cinema_settings SET booking_days_ahead = :new "
            "WHERE booking_days_ahead = :old"
        ).bindparams(new=NEW_DEFAULT, old=OLD_DEFAULT)
    )


def downgrade() -> None:
    with op.batch_alter_table("cinema_settings") as batch:
        batch.alter_column(
            "booking_days_ahead",
            existing_type=sa.Integer(),
            server_default=str(OLD_DEFAULT),
        )
    op.execute(
        sa.text(
            "UPDATE cinema_settings SET booking_days_ahead = :old "
            "WHERE booking_days_ahead = :new"
        ).bindparams(old=OLD_DEFAULT, new=NEW_DEFAULT)
    )
