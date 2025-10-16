import asyncio
import logging
import shutil
import sys
from pathlib import Path
from typing import Iterable

from pymilvus import Collection, utility

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from infrastructure.database.database import create_tables, drop_tables, engine  # noqa: E402
from infrastructure.database.setup import (  # noqa: E402
    configure_multi_tenant_rls,
    seed_default_tenant_and_project,
)
from infrastructure.vector_store.milvus.milvus_client import MilvusClientFactory  # noqa: E402

logger = logging.getLogger("reset_state")


async def reset_database() -> None:
    logger.info("Dropping database tables...")
    await drop_tables()

    logger.info("Recreating database tables...")
    await create_tables()

    async with engine.begin() as conn:
        logger.info("Configuring multi-tenant RLS policies...")
        await configure_multi_tenant_rls(conn)

    logger.info("Seeding default tenant and project...")
    await seed_default_tenant_and_project()


async def _drop_milvus_collection(alias: str, collection_name: str) -> None:
    loop = asyncio.get_event_loop()

    def _drop() -> None:
        if utility.has_collection(collection_name, using=alias):
            collection = Collection(collection_name, using=alias)
            collection.release()
            collection.drop()
            logger.info("Dropped Milvus collection '%s'", collection_name)
        else:
            logger.info("Milvus collection '%s' does not exist; skipping.", collection_name)

    await loop.run_in_executor(None, _drop)


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

    collection_names: Iterable[str] = {
        settings.MILVUS_COLLECTION_NAME,
        getattr(settings, "MILVUS_DOCUMENT_SUMMARY_COLLECTION_NAME", "document_summary_vectors"),
        getattr(settings, "MILVUS_PROJECT_SUMMARY_COLLECTION_NAME", "project_summary_vectors"),
    }

    for name in collection_names:
        if not name:
            continue
        await _drop_milvus_collection(alias, name)

    await factory.close()


async def reset_document_files() -> None:
    git_repo_path = settings.GIT_REPO_PATH
    if not git_repo_path:
        logger.info("GIT_REPO_PATH not set; skipping document file cleanup.")
        return

    documents_dir = (Path(git_repo_path).resolve() / "documents").expanduser()
    loop = asyncio.get_event_loop()

    def _reset_directory() -> None:
        if documents_dir.exists():
            shutil.rmtree(documents_dir)
        documents_dir.mkdir(parents=True, exist_ok=True)

    await loop.run_in_executor(None, _reset_directory)
    logger.info("Cleared document files at '%s'", documents_dir)


async def main() -> None:
    try:
        await reset_database()
        await reset_milvus()
        await reset_document_files()
        logger.info("State reset complete.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    asyncio.run(main())
