"""Stage: seed the cinema's Yandex Maps deep link into map_url.

`map_url` was added empty in 0012 (spec 4.9 lets the admin fill it in). The
cinema now has a real Yandex Maps deep link to show by default, so this
backfills any row that still has the untouched empty value and updates the
column's server default for any row inserted afterwards outside the ORM.
Rows the admin has already customised (non-empty map_url) are left alone.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_settings_map_url_default"
down_revision = "0014_timezone_and_one_review"
branch_labels = None
depends_on = None

DEFAULT_MAP_URL = "https://yandex.go.link/discovery?action=card&oid=97603506332&adj_campaign=Share-from-the-app"


def upgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("cinema_settings") as batch:
        batch.alter_column(
            "map_url",
            existing_type=sa.String(512),
            server_default=DEFAULT_MAP_URL,
        )
    bind.execute(
        sa.text("UPDATE cinema_settings SET map_url = :url WHERE map_url = ''").bindparams(
            url=DEFAULT_MAP_URL
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE cinema_settings SET map_url = '' WHERE map_url = :url").bindparams(
            url=DEFAULT_MAP_URL
        )
    )
    with op.batch_alter_table("cinema_settings") as batch:
        batch.alter_column(
            "map_url",
            existing_type=sa.String(512),
            server_default="",
        )
