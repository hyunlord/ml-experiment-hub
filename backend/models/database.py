"""Database configuration and session management."""

import asyncio
import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from backend.config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_LEVEL == "DEBUG",
    future=True,
)

# Create async session factory
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _run_alembic_upgrade() -> None:
    """Run Alembic migrations synchronously (meant to be called in a thread)."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


async def init_db() -> None:
    """Initialize database — run Alembic migrations, fallback to create_all."""
    try:
        await asyncio.to_thread(_run_alembic_upgrade)
        logger.info("Alembic migrations applied successfully")
    except Exception as e:
        logger.warning("Alembic migration skipped (%s), using create_all fallback", e)
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async with async_session_maker() as session:
        yield session
