"""Stage 6: bot handle used to build share deep links."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_settings_bot_username"
down_revision = "0012_settings_shows_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cinema_settings",
        sa.Column("bot_username", sa.String(64), nullable=False, server_default=""),
    )


def downgrade() -> None:
    with op.batch_alter_table("cinema_settings") as batch:
        batch.drop_column("bot_username")
