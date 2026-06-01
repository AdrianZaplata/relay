"""Async database engine and session wiring.

`create_async_engine` is lazy (no connection at import), so importing this module
is safe without a live database — tests override `get_session` with a SQLite
engine and never touch this one.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .models import Base

log = logging.getLogger("relay.db")

engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_models(retries: int = 10, delay: float = 1.5) -> None:
    """Create tables, retrying while the database comes up (compose start order).

    create_all is fine for this demo; production would use Alembic migrations
    so schema changes ship through the same merge->review->deploy pipeline.
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
                await conn.run_sync(Base.metadata.create_all)
            return
        except Exception as exc:  # noqa: BLE001 - retry any startup connection error
            last_exc = exc
            log.warning("db not ready (attempt %d/%d): %s", attempt, retries, exc)
            await asyncio.sleep(delay)
    raise RuntimeError("database did not become ready") from last_exc


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
