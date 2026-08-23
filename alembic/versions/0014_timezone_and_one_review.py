"""Stage 14: cinema timezone, and one review per viewer per movie.

The timezone is what lets the server tell whether a screening has finished:
it runs in UTC while the cinema lives at UTC+5.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_timezone_and_one_review"
down_revision = "0013_settings_bot_username"
branch_labels = None
depends_on = None

#: Uzbekistan is UTC+5 and does not observe daylight saving, so a fixed offset
#: is exact there. Stored in minutes to allow half-hour zones later.
DEFAULT_OFFSET_MINUTES = 300


def upgrade() -> None:
    op.add_column(
        "cinema_settings",
        sa.Column(
            "timezone_offset_minutes",
            sa.Integer(),
            nullable=False,
            server_default=str(DEFAULT_OFFSET_MINUTES),
        ),
    )

    # Keep the newest review per (user, movie) before the constraint goes on.
    op.execute(
        sa.text(
            "DELETE FROM reviews WHERE id NOT IN ("
            " SELECT MAX(id) FROM reviews GROUP BY user_id, movie_id"
            ")"
        )
    )
    with op.batch_alter_table("reviews") as batch:
        batch.create_unique_constraint("uq_review_per_movie", ["user_id", "movie_id"])


def downgrade() -> None:
    with op.batch_alter_table("reviews") as batch:
        batch.drop_constraint("uq_review_per_movie", type_="unique")
    with op.batch_alter_table("cinema_settings") as batch:
        batch.drop_column("timezone_offset_minutes")
