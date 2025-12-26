from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import get_settings


class Base(DeclarativeBase):
    """Base class for ORM models."""


def _build_engine():
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, echo=False, future=True)


engine = _build_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Create tables if they do not exist."""
    # Import models so they are registered on the Base metadata before create_all.
    import infrastructure.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency to provide an async DB session."""
    async with SessionLocal() as session:
        yield session
