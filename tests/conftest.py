import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api import router
from app.database import Base, get_db


@pytest.fixture(scope="session")
def event_loop() -> AsyncIterator[asyncio.AbstractEventLoop]:
    """Create an event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Persistent SQLite database file for the test session."""
    return tmp_path_factory.mktemp("data") / "test.db"


@pytest.fixture(scope="session")
async def test_engine(db_path: Path) -> AsyncIterator[AsyncEngine]:
    """Async engine bound to a SQLite database for tests."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        future=True,
        echo=False,
        poolclass=NullPool,
    )

    # Ensure schema exists once per session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def reset_db(test_engine: AsyncEngine) -> None:
    """Reset database state before each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
async def session_factory(
    test_engine: AsyncEngine, reset_db: None
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Yield an async session factory bound to the test engine."""
    yield async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncSession]:
    """Provide a database session for database-focused tests."""
    async with session_factory() as session:
        yield session


@pytest.fixture
async def test_app(
    session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[FastAPI]:
    """FastAPI application instance wired to the test database."""
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def _get_test_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db

    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def api_client(test_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Reusable HTTP client for interacting with the FastAPI app."""
    async with AsyncClient(app=test_app, base_url="http://testserver") as client:
        yield client
