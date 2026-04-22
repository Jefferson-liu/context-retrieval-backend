from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass

from config.settings import get_settings
from infrastructure.database import SessionLocal
from infrastructure.repositories import RepoRunRepository
from services.repo_knowledge.ingestion_service import RepoIngestionWorker

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RepoIngestionQueueItem:
    """One queued ingestion task."""

    run_id: str
    force_reingest: bool = False
    git_token: str | None = None


class RepoIngestionBackgroundRunner:
    """In-process async runner for queued repository ingestion runs."""

    def __init__(self, *, max_concurrent_runs: int) -> None:
        self.max_concurrent_runs = max(1, max_concurrent_runs)
        self._queue: asyncio.Queue[RepoIngestionQueueItem] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        """Start worker tasks and recover stale runs."""
        if self._started:
            logger.debug("Repo ingestion runner start skipped (already started)")
            return
        self._started = True
        logger.info("Repo ingestion runner starting workers=%s", self.max_concurrent_runs)

        async with SessionLocal() as session:
            run_repo = RepoRunRepository(session)
            stale_count = await run_repo.mark_stale_runs_failed()
            if stale_count:
                logger.warning("Marked %s stale repo ingestion runs as failed", stale_count)
            await session.commit()

        for idx in range(self.max_concurrent_runs):
            task = asyncio.create_task(self._worker_loop(worker_id=idx), name=f"repo-ingestion-worker-{idx}")
            self._workers.append(task)
            logger.info("Repo ingestion worker started worker_id=%s", idx)

    async def stop(self) -> None:
        """Stop workers gracefully."""
        if not self._started:
            logger.debug("Repo ingestion runner stop skipped (not started)")
            return
        logger.info("Repo ingestion runner stopping workers=%s", len(self._workers))
        self._started = False
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            with suppress(asyncio.CancelledError):
                await task
        self._workers.clear()
        logger.info("Repo ingestion runner stopped")

    async def enqueue(self, run_id: str, *, force_reingest: bool = False, git_token: str | None = None) -> None:
        """Queue a run for background processing."""
        await self._queue.put(
            RepoIngestionQueueItem(
                run_id=run_id,
                force_reingest=force_reingest,
                git_token=git_token,
            )
        )
        logger.info(
            "Repo ingestion run enqueued run_id=%s force_reingest=%s queue_size=%s",
            run_id,
            force_reingest,
            self._queue.qsize(),
        )

    async def _worker_loop(self, *, worker_id: int) -> None:
        while True:
            item = await self._queue.get()
            logger.info(
                "Repo ingestion worker picked run worker_id=%s run_id=%s force_reingest=%s",
                worker_id,
                item.run_id,
                item.force_reingest,
            )
            try:
                async with SessionLocal() as session:
                    worker = RepoIngestionWorker(session)
                    await worker.execute(run_id=item.run_id, force_reingest=item.force_reingest, git_token=item.git_token)
                    logger.info(
                        "Repo ingestion worker finished run worker_id=%s run_id=%s force_reingest=%s",
                        worker_id,
                        item.run_id,
                        item.force_reingest,
                    )
            except Exception:
                logger.exception("Worker %s failed processing run %s", worker_id, item.run_id)
            finally:
                self._queue.task_done()


_runner: RepoIngestionBackgroundRunner | None = None


def get_repo_ingestion_runner() -> RepoIngestionBackgroundRunner:
    """Return singleton runner instance."""
    global _runner
    if _runner is None:
        settings = get_settings()
        _runner = RepoIngestionBackgroundRunner(
            max_concurrent_runs=settings.REPO_INGEST_MAX_CONCURRENT_RUNS,
        )
    return _runner
