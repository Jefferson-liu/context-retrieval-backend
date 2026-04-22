from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from config.settings import get_settings
from infrastructure.database import SessionLocal
from infrastructure.repositories import RepoFileSummaryRunRepository
from services.repo_knowledge.file_summary_service import RepoFileSummaryWorker

logger = logging.getLogger(__name__)


class RepoFileSummaryBackgroundRunner:
    """In-process async runner for queued repository summary file_summary runs."""

    def __init__(self, *, max_concurrent_runs: int) -> None:
        self.max_concurrent_runs = max(1, max_concurrent_runs)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        """Start worker tasks and recover stale file_summary runs."""
        if self._started:
            logger.debug("Repo file_summary runner start skipped (already started)")
            return
        self._started = True
        logger.info("Repo file_summary runner starting workers=%s", self.max_concurrent_runs)

        async with SessionLocal() as session:
            repo = RepoFileSummaryRunRepository(session)
            stale_count = await repo.mark_stale_runs_failed()
            if stale_count:
                logger.warning("Marked %s stale repo file_summary runs as failed", stale_count)
            await session.commit()

        for idx in range(self.max_concurrent_runs):
            task = asyncio.create_task(self._worker_loop(worker_id=idx), name=f"repo-file_summary-worker-{idx}")
            self._workers.append(task)
            logger.info("Repo file_summary worker started worker_id=%s", idx)

    async def stop(self) -> None:
        """Stop workers gracefully."""
        if not self._started:
            logger.debug("Repo file_summary runner stop skipped (not started)")
            return
        logger.info("Repo file_summary runner stopping workers=%s", len(self._workers))
        self._started = False
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            with suppress(asyncio.CancelledError):
                await task
        self._workers.clear()
        logger.info("Repo file_summary runner stopped")

    async def enqueue(self, file_summary_run_id: str) -> None:
        """Queue a summary file_summary run for background processing."""
        await self._queue.put(file_summary_run_id)
        logger.info(
            "Repo file_summary run enqueued file_summary_run_id=%s queue_size=%s",
            file_summary_run_id,
            self._queue.qsize(),
        )

    async def _worker_loop(self, *, worker_id: int) -> None:
        while True:
            file_summary_run_id = await self._queue.get()
            logger.info(
                "Repo file_summary worker picked run worker_id=%s file_summary_run_id=%s",
                worker_id,
                file_summary_run_id,
            )
            try:
                async with SessionLocal() as session:
                    worker = RepoFileSummaryWorker(session)
                    await worker.execute(file_summary_run_id=file_summary_run_id)
                    logger.info(
                        "Repo file_summary worker finished run worker_id=%s file_summary_run_id=%s",
                        worker_id,
                        file_summary_run_id,
                    )
            except Exception:
                logger.exception(
                    "Repo file_summary worker %s failed processing run %s",
                    worker_id,
                    file_summary_run_id,
                )
            finally:
                self._queue.task_done()


_runner: RepoFileSummaryBackgroundRunner | None = None


def get_repo_file_summary_runner() -> RepoFileSummaryBackgroundRunner:
    """Return singleton summary file_summary runner instance."""
    global _runner
    if _runner is None:
        settings = get_settings()
        _runner = RepoFileSummaryBackgroundRunner(
            max_concurrent_runs=settings.REPO_SUMMARY_MAX_CONCURRENT_RUNS,
        )
    return _runner
