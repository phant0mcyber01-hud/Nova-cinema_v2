"""FAQ and the "important to know" note actually persist.

The admin form has always had inputs for these -- there was simply no column
to write them into, so PUT /api/admin/settings silently dropped both (pydantic
drops unrecognised fields) and the panel looked like it saved when it had not
written anything at all. This adds the columns the model and the request
schema now expect; no existing settings row loses any other data.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_settings_important_and_faq"
down_revision = "0020_booking_window_eight_days"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cinema_settings", sa.Column("important", sa.Text(), nullable=False, server_default=""))
    op.add_column("cinema_settings", sa.Column("important_uz", sa.Text(), nullable=False, server_default=""))
    op.add_column("cinema_settings", sa.Column("faq_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("cinema_settings") as batch:
        batch.drop_column("faq_json")
        batch.drop_column("important_uz")
        batch.drop_column("important")
