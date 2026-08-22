import asyncio
import sys
from pathlib import Path
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.core.config import DATABASE_URL
from backend.core.db import Base
import backend.models  # noqa: F401  -- registers every table

config = context.config
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction(): context.run_migrations()

def widen_version_column(connection) -> None:
    """Make room for this project's revision identifiers.

    Alembic creates alembic_version.version_num as VARCHAR(32), and
    `0011_movie_i18n_booking_proposals` is 33 characters. SQLite does not
    enforce the length, so development and the test suite never noticed; on
    PostgreSQL — the production database — the upgrade died halfway through
    with "value too long for type character varying(32)", leaving the schema
    part migrated. The table is created here first, wide enough, and Alembic
    then reuses it instead of creating its own.
    """
    if connection.dialect.name != "postgresql":
        return
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS alembic_version ("
        " version_num VARCHAR(64) NOT NULL,"
        " CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
    )
    connection.exec_driver_sql(
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"
    )


def do_run_migrations(connection) -> None:
    widen_version_column(connection)
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction(): context.run_migrations()

async def run_migrations_online() -> None:
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
        # Without this the whole upgrade is rolled back on close. SQLite hid it
        # by committing DDL as it went; PostgreSQL wraps every migration in one
        # transaction, so `alembic upgrade head` finished quietly, reported
        # success and left the database empty — including in the Docker image,
        # which runs exactly this command before starting the API.
        await connection.commit()
    await engine.dispose()

if context.is_offline_mode(): run_migrations_offline()
else: asyncio.run(run_migrations_online())
