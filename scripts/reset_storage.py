from __future__ import annotations

import argparse
import asyncio
import logging

from infrastructure.database import Base, engine

logger = logging.getLogger(__name__)


def _load_models() -> None:
    """Import ORM models so Base.metadata is fully populated."""
    import infrastructure.models  # noqa: F401


async def reset_relational_store() -> None:
    """
    Drop and recreate all SQL tables.

    This is destructive and should only be used for local resets or fresh test fixtures.
    """
    _load_models()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Relational tables dropped and recreated.")


async def run(force: bool) -> None:
    """Entry point for resetting storage with optional confirmation."""
    if not force:
        confirmation = input(
            "This will DROP all database tables. Continue? [y/N]: "
        )
        if confirmation.strip().lower() not in {"y", "yes"}:
            print("Aborting reset.")
            return
    await reset_relational_store()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Drop all SQL tables for a clean local environment."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    asyncio.run(run(force=args.force))
