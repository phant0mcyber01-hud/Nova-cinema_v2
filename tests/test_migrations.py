"""Stage 20: the migration chain, walked in both directions.

Every stage of the spec added migrations, and each one was checked when it was
written. What was never checked is the whole chain: a downgrade only has to get
one index wrong for a rollback to die halfway, in production, with the schema
already half torn down. So the chain is walked here from an empty database up
to head, all the way back down to base, and up again.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSIONS = PROJECT_ROOT / "alembic" / "versions"


def _alembic(*args: str, database_url: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "DATABASE_URL": database_url, "AUTO_CREATE_SCHEMA": "false"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def database_url(tmp_path: pathlib.Path) -> str:
    return f"sqlite+aiosqlite:///{(tmp_path / 'chain.db').as_posix()}"


def test_the_chain_is_linear_with_a_single_head():
    heads = _alembic("heads", database_url="sqlite+aiosqlite:///:memory:")
    assert heads.returncode == 0, heads.stderr
    assert len([line for line in heads.stdout.splitlines() if line.strip()]) == 1, (
        f"a branched history cannot be upgraded unattended:\n{heads.stdout}"
    )


def test_every_revision_declares_a_downgrade():
    for path in sorted(VERSIONS.glob("[0-9]*.py")):
        source = path.read_text(encoding="utf-8")
        assert "def downgrade()" in source, f"{path.name} cannot be rolled back"


@pytest.mark.slow
def test_an_empty_database_can_be_upgraded_and_rolled_all_the_way_back(database_url):
    up = _alembic("upgrade", "head", database_url=database_url)
    assert up.returncode == 0, up.stderr

    down = _alembic("downgrade", "base", database_url=database_url)
    assert down.returncode == 0, f"the rollback path is broken:\n{down.stderr}"

    again = _alembic("upgrade", "head", database_url=database_url)
    assert again.returncode == 0, f"the schema cannot be rebuilt after a rollback:\n{again.stderr}"

    current = _alembic("current", database_url=database_url)
    assert "(head)" in current.stdout


def test_revision_ids_fit_the_version_table():
    """Alembic's own table caps the identifier; PostgreSQL enforces the cap.

    SQLite ignores VARCHAR lengths, so an over-long revision id passes every
    local check and then breaks the production upgrade halfway through. The
    project widens the column in env.py; this keeps both halves honest.
    """
    env = (PROJECT_ROOT / "alembic" / "env.py").read_text(encoding="utf-8")
    assert "VARCHAR(64)" in env, "env.py must prepare a version table wide enough"

    for path in sorted(VERSIONS.glob("[0-9]*.py")):
        match = re.search(r'^revision\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"), re.M)
        assert match, f"{path.name} declares no revision id"
        assert len(match.group(1)) <= 64, f"{match.group(1)} does not fit the widened column"
