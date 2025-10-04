import asyncio
import logging
import sys
from pathlib import Path

from pymilvus import Collection, utility

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from infrastructure.database.database import create_tables, drop_tables, engine
from infrastructure.database.setup import configure_multi_tenant_rls, seed_default_tenant_and_project
from infrastructure.vector_store.milvus.milvus_client import MilvusClientFactory

logger = logging.getLogger("reset_state")


async def reset_database() -> None:
    logger.info("Dropping database tables…")
    await drop_tables()
    logger.info("Recreating database tables…")
    await create_tables()

    async with engine.begin() as conn:
        logger.info("Configuring multi-tenant RLS policies…")
        await configure_multi_tenant_rls(conn)

    logger.info("Seeding default tenant and project…")
    await seed_default_tenant_and_project()


async def reset_milvus() -> None:
    if settings.VECTOR_STORE_MODE != "milvus":
        logger.info("VECTOR_STORE_MODE != 'milvus'; skipping Milvus reset.")
        return

    factory = MilvusClientFactory(
        host=settings.MILVUS_HOST,
        port=settings.MILVUS_PORT,
        username=settings.MILVUS_USERNAME,
        password=settings.MILVUS_PASSWORD,
    )

    alias = await factory.ensure_connection()
    collection_name = settings.MILVUS_COLLECTION_NAME
    loop = asyncio.get_event_loop()

    def _drop_collection() -> None:
        if utility.has_collection(collection_name, using=alias):
            collection = Collection(collection_name, using=alias)
            collection.release()
            collection.drop()
            logger.info("Dropped Milvus collection '%s'", collection_name)
        else:
            logger.info("Milvus collection '%s' does not exist; nothing to drop.", collection_name)

    await loop.run_in_executor(None, _drop_collection)


async def main() -> None:
    await reset_database()
    await reset_milvus()
    await engine.dispose()
    logger.info("State reset complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
