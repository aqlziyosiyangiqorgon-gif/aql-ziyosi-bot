"""Pytest configuration and async fixtures."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram import Bot
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import gatebot.db.session as session_module
from gatebot.config import Settings
from gatebot.db.models import Base


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_placeholder",
        ADMIN_IDS=[111222333, 999888777],
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        SUB_CACHE_SECONDS=60,
        TIMEZONE="Asia/Tashkent",
        LOG_LEVEL="DEBUG",
    )


@pytest_asyncio.fixture
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Patch global sessionmaker
    sm = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    session_module._engine = engine
    session_module._sessionmaker = sm

    yield engine

    await engine.dispose()
    session_module._engine = None
    session_module._sessionmaker = None


@pytest_asyncio.fixture
async def db_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    sm = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with sm() as session:
        yield session


@pytest.fixture
def mock_bot() -> AsyncMock:
    bot = AsyncMock(spec=Bot)
    bot.approve_chat_join_request = AsyncMock()
    bot.decline_chat_join_request = AsyncMock()
    bot.send_message = AsyncMock()
    bot.leave_chat = AsyncMock()
    bot.get_chat_member = AsyncMock()
    bot.get_chat = AsyncMock()
    return bot
