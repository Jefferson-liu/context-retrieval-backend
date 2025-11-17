from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from config import settings


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(64) NOT NULL PRIMARY KEY
                )
                """
            )
        )
        await conn.execute(text("DELETE FROM alembic_version"))
        await conn.execute(
            text("INSERT INTO alembic_version(version_num) VALUES (:rev)"),
            {"rev": "20251115_temporal_knowledge_tables"},
        )
    await engine.dispose()

    print("Seeded alembic_version with 20251115_temporal_knowledge_tables")


if __name__ == "__main__":
    asyncio.run(main())
