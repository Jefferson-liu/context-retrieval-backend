from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from config.settings import get_settings
from infrastructure.database import SessionLocal
from infrastructure.repositories import RepoFullSummaryRunRepository
from services.repo_knowledge.repo_full_summary_service import RepoFullSummaryWorker

logger = logging.getLogger(__name__)


class RepoFullSummaryBackgroundRunner:
    """In-process async runner for queued repo full-summary runs."""

    def __init__(self, *, max_concurrent_runs: int) -> None:
        self.max_concurrent_runs = max(1, max_concurrent_runs)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        """Start worker tasks and recover stale repo-full-summary runs."""
        if self._started:
            logger.debug("Repo full-summary runner start skipped (already started)")
            return
        self._started = True
        logger.info("Repo full-summary runner starting workers=%s", self.max_concurrent_runs)

        async with SessionLocal() as session:
            repo = RepoFullSummaryRunRepository(session)
            stale_count = await repo.mark_stale_runs_failed()
            if stale_count:
                logger.warning("Marked %s stale repo full-summary runs as failed", stale_count)
            await session.commit()

        for idx in range(self.max_concurrent_runs):
            task = asyncio.create_task(self._worker_loop(worker_id=idx), name=f"repo-full-summary-worker-{idx}")
            self._workers.append(task)
            logger.info("Repo full-summary worker started worker_id=%s", idx)

    async def stop(self) -> None:
        """Stop workers gracefully."""
        if not self._started:
            logger.debug("Repo full-summary runner stop skipped (not started)")
            return
        logger.info("Repo full-summary runner stopping workers=%s", len(self._workers))
        self._started = False
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            with suppress(asyncio.CancelledError):
                await task
        self._workers.clear()
        logger.info("Repo full-summary runner stopped")

    async def enqueue(self, repo_full_summary_run_id: str) -> None:
        """Queue a repo full-summary run for background processing."""

        await self._queue.put(repo_full_summary_run_id)
        logger.info(
            "Repo full-summary run enqueued repo_full_summary_run_id=%s queue_size=%s",
            repo_full_summary_run_id,
            self._queue.qsize(),
        )

    async def _worker_loop(self, *, worker_id: int) -> None:
        while True:
            repo_full_summary_run_id = await self._queue.get()
            logger.info(
                "Repo full-summary worker picked run worker_id=%s repo_full_summary_run_id=%s",
                worker_id,
                repo_full_summary_run_id,
            )
            try:
                async with SessionLocal() as session:
                    worker = RepoFullSummaryWorker(session)
                    await worker.execute(repo_full_summary_run_id=repo_full_summary_run_id)
                    logger.info(
                        "Repo full-summary worker finished run worker_id=%s repo_full_summary_run_id=%s",
                        worker_id,
                        repo_full_summary_run_id,
                    )
            except Exception:
                logger.exception(
                    "Repo full-summary worker %s failed processing run %s",
                    worker_id,
                    repo_full_summary_run_id,
                )
            finally:
                self._queue.task_done()


_runner: RepoFullSummaryBackgroundRunner | None = None


def get_repo_full_summary_runner() -> RepoFullSummaryBackgroundRunner:
    """Return singleton repo full-summary runner instance."""

    global _runner
    if _runner is None:
        settings = get_settings()
        _runner = RepoFullSummaryBackgroundRunner(
            max_concurrent_runs=settings.REPO_FULL_SUMMARY_MAX_CONCURRENT_RUNS,
        )
    return _runner
