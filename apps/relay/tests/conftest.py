"""Test fixtures: an isolated SQLite database per test, and an httpx client
wired to the FastAPI app with the DB dependency overridden.

Using ASGITransport means the app's lifespan does NOT run, so tests never touch
the production Postgres engine — they run fully self-contained against SQLite.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from relay.api import app
from relay.db import get_session
from relay.models import Base


@pytest_asyncio.fixture
async def engine(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    eng = create_async_engine(url, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
