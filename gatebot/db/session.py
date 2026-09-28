"""Async database engine and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import logging
import os

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def ensure_sqlite_dir(database_url: str) -> None:
    """Ensure parent directory exists for SQLite database URLs."""
    if "sqlite" in database_url:
        try:
            path_part = database_url.split("///")[-1]
            if "?" in path_part:
                path_part = path_part.split("?")[0]
            db_dir = os.path.dirname(path_part)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        except Exception as e:
            logger.warning("Could not auto-create database directory: %s", e)


def init_engine(database_url: str) -> AsyncEngine:
    """Initialize async SQLAlchemy engine and session factory."""
    global _engine, _sessionmaker
    ensure_sqlite_dir(database_url)
    _engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
    )
    _sessionmaker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _engine


def get_engine() -> AsyncEngine:
    """Get active database engine."""
    if _engine is None:
        raise RuntimeError("Database engine is not initialized. Call init_engine() first.")
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Get active session factory."""
    if _sessionmaker is None:
        raise RuntimeError("Sessionmaker is not initialized. Call init_engine() first.")
    return _sessionmaker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Dispose active database engine connections."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
