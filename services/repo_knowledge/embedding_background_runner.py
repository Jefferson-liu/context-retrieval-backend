from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from config.settings import get_settings
from infrastructure.database import SessionLocal
from infrastructure.repositories import RepoEmbeddingRunRepository
from services.repo_knowledge.embedding_service import RepoEmbeddingWorker

logger = logging.getLogger(__name__)


class RepoEmbeddingBackgroundRunner:
    """In-process async runner for queued repository embedding runs."""

    def __init__(self, *, max_concurrent_runs: int) -> None:
        self.max_concurrent_runs = max(1, max_concurrent_runs)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        """Start worker tasks and recover stale embedding runs."""
        if self._started:
            logger.debug("Repo embedding runner start skipped (already started)")
            return
        self._started = True
        logger.info("Repo embedding runner starting workers=%s", self.max_concurrent_runs)

        async with SessionLocal() as session:
            repo = RepoEmbeddingRunRepository(session)
            stale_count = await repo.mark_stale_runs_failed()
            if stale_count:
                logger.warning("Marked %s stale repo embedding runs as failed", stale_count)
            await session.commit()

        for idx in range(self.max_concurrent_runs):
            task = asyncio.create_task(self._worker_loop(worker_id=idx), name=f"repo-embedding-worker-{idx}")
            self._workers.append(task)
            logger.info("Repo embedding worker started worker_id=%s", idx)

    async def stop(self) -> None:
        """Stop workers gracefully."""
        if not self._started:
            logger.debug("Repo embedding runner stop skipped (not started)")
            return
        logger.info("Repo embedding runner stopping workers=%s", len(self._workers))
        self._started = False
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            with suppress(asyncio.CancelledError):
                await task
        self._workers.clear()
        logger.info("Repo embedding runner stopped")

    async def enqueue(self, embedding_run_id: str) -> None:
        """Queue an embedding run for background processing."""
        await self._queue.put(embedding_run_id)
        logger.info(
            "Repo embedding run enqueued embedding_run_id=%s queue_size=%s",
            embedding_run_id,
            self._queue.qsize(),
        )

    async def _worker_loop(self, *, worker_id: int) -> None:
        while True:
            embedding_run_id = await self._queue.get()
            logger.info(
                "Repo embedding worker picked run worker_id=%s embedding_run_id=%s",
                worker_id,
                embedding_run_id,
            )
            try:
                async with SessionLocal() as session:
                    worker = RepoEmbeddingWorker(session)
                    await worker.execute(embedding_run_id=embedding_run_id)
                    logger.info(
                        "Repo embedding worker finished run worker_id=%s embedding_run_id=%s",
                        worker_id,
                        embedding_run_id,
                    )
            except Exception:
                logger.exception(
                    "Repo embedding worker %s failed processing run %s",
                    worker_id,
                    embedding_run_id,
                )
            finally:
                self._queue.task_done()


_runner: RepoEmbeddingBackgroundRunner | None = None


def get_repo_embedding_runner() -> RepoEmbeddingBackgroundRunner:
    """Return singleton embedding runner instance."""
    global _runner
    if _runner is None:
        settings = get_settings()
        _runner = RepoEmbeddingBackgroundRunner(max_concurrent_runs=settings.REPO_EMBED_MAX_CONCURRENT_RUNS)
    return _runner
