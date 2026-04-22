from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from config.settings import get_settings
from infrastructure.database import SessionLocal
from infrastructure.repositories import RepoGroupSummaryRunRepository
from services.repo_knowledge.group_summary_service import RepoGroupSummaryWorker

logger = logging.getLogger(__name__)


class RepoGroupSummaryBackgroundRunner:
    """In-process async runner for queued repository group-summary runs."""

    def __init__(self, *, max_concurrent_runs: int) -> None:
        self.max_concurrent_runs = max(1, max_concurrent_runs)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        """Start worker tasks and recover stale group-summary runs."""
        if self._started:
            logger.debug("Repo group-summary runner start skipped (already started)")
            return
        self._started = True
        logger.info("Repo group-summary runner starting workers=%s", self.max_concurrent_runs)

        async with SessionLocal() as session:
            repo = RepoGroupSummaryRunRepository(session)
            stale_count = await repo.mark_stale_runs_failed()
            if stale_count:
                logger.warning("Marked %s stale repo group-summary runs as failed", stale_count)
            await session.commit()

        for idx in range(self.max_concurrent_runs):
            task = asyncio.create_task(self._worker_loop(worker_id=idx), name=f"repo-group-summary-worker-{idx}")
            self._workers.append(task)
            logger.info("Repo group-summary worker started worker_id=%s", idx)

    async def stop(self) -> None:
        """Stop workers gracefully."""
        if not self._started:
            logger.debug("Repo group-summary runner stop skipped (not started)")
            return
        logger.info("Repo group-summary runner stopping workers=%s", len(self._workers))
        self._started = False
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            with suppress(asyncio.CancelledError):
                await task
        self._workers.clear()
        logger.info("Repo group-summary runner stopped")

    async def enqueue(self, group_summary_run_id: str) -> None:
        """Queue a group-summary run for background processing."""
        await self._queue.put(group_summary_run_id)
        logger.info(
            "Repo group-summary run enqueued group_summary_run_id=%s queue_size=%s",
            group_summary_run_id,
            self._queue.qsize(),
        )

    async def _worker_loop(self, *, worker_id: int) -> None:
        while True:
            group_summary_run_id = await self._queue.get()
            logger.info(
                "Repo group-summary worker picked run worker_id=%s group_summary_run_id=%s",
                worker_id,
                group_summary_run_id,
            )
            try:
                async with SessionLocal() as session:
                    worker = RepoGroupSummaryWorker(session)
                    await worker.execute(group_summary_run_id=group_summary_run_id)
                    logger.info(
                        "Repo group-summary worker finished run worker_id=%s group_summary_run_id=%s",
                        worker_id,
                        group_summary_run_id,
                    )
            except Exception:
                logger.exception(
                    "Repo group-summary worker %s failed processing run %s",
                    worker_id,
                    group_summary_run_id,
                )
            finally:
                self._queue.task_done()


_runner: RepoGroupSummaryBackgroundRunner | None = None


def get_repo_group_summary_runner() -> RepoGroupSummaryBackgroundRunner:
    """Return singleton group-summary background runner instance."""
    global _runner
    if _runner is None:
        settings = get_settings()
        _runner = RepoGroupSummaryBackgroundRunner(
            max_concurrent_runs=settings.REPO_GROUP_SUMMARY_MAX_CONCURRENT_RUNS,
        )
    return _runner
