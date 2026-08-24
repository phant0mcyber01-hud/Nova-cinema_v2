"""Add the independently managed movie hits flag."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_movie_hits"
down_revision = "0015_settings_map_url_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "movies",
        sa.Column("is_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_movies_is_hit", "movies", ["is_hit"])


def downgrade() -> None:
    op.drop_index("ix_movies_is_hit", table_name="movies")
    with op.batch_alter_table("movies") as batch:
        batch.drop_column("is_hit")
