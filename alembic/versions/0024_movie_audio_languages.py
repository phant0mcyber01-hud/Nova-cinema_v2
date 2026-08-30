"""Add movie audio_languages so the admin can mark which dubs exist."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_movie_audio_languages"
down_revision = "0023_viewer_history_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "movies",
        sa.Column("audio_languages", sa.String(length=32), nullable=False, server_default="ru,uz"),
    )


def downgrade() -> None:
    with op.batch_alter_table("movies") as batch:
        batch.drop_column("audio_languages")
