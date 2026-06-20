"""Integration fixtures: ephemeral Postgres via testcontainers + migrated schema.

Skips the whole module if Docker / testcontainers is unavailable so unit CI stays green.
"""

from __future__ import annotations

import pytest

pytest.importorskip("testcontainers.postgres")

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402

from postpilot.models import Base  # noqa: E402


@pytest.fixture(scope="session")
def pg_url():
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest.fixture
async def sessionmaker(pg_url):
    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield sm
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
