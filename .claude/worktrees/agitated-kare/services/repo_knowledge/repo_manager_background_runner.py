from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from config.settings import get_settings
from infrastructure.database import SessionLocal
from infrastructure.repositories import RepoManagerRunRepository
from services.repo_knowledge.repo_manager_service import RepoManagerWorker

logger = logging.getLogger(__name__)


class RepoManagerBackgroundRunner:
    """In-process async runner for queued repo-manager runs."""

    def __init__(self, *, max_concurrent_runs: int) -> None:
        self.max_concurrent_runs = max(1, max_concurrent_runs)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            logger.debug("Repo manager runner start skipped (already started)")
            return
        self._started = True
        logger.info("Repo manager runner starting workers=%s", self.max_concurrent_runs)

        async with SessionLocal() as session:
            repo = RepoManagerRunRepository(session)
            stale_count = await repo.mark_stale_runs_failed()
            if stale_count:
                logger.warning("Marked %s stale repo-manager runs as failed", stale_count)
            await session.commit()

        for idx in range(self.max_concurrent_runs):
            task = asyncio.create_task(self._worker_loop(worker_id=idx), name=f"repo-manager-worker-{idx}")
            self._workers.append(task)
            logger.info("Repo manager worker started worker_id=%s", idx)

    async def stop(self) -> None:
        if not self._started:
            logger.debug("Repo manager runner stop skipped (not started)")
            return
        logger.info("Repo manager runner stopping workers=%s", len(self._workers))
        self._started = False
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            with suppress(asyncio.CancelledError):
                await task
        self._workers.clear()
        logger.info("Repo manager runner stopped")

    async def enqueue(self, repo_manager_run_id: str) -> None:
        await self._queue.put(repo_manager_run_id)
        logger.info(
            "Repo manager run enqueued repo_manager_run_id=%s queue_size=%s",
            repo_manager_run_id,
            self._queue.qsize(),
        )

    async def _worker_loop(self, *, worker_id: int) -> None:
        while True:
            repo_manager_run_id = await self._queue.get()
            logger.info(
                "Repo manager worker picked run worker_id=%s repo_manager_run_id=%s",
                worker_id,
                repo_manager_run_id,
            )
            try:
                async with SessionLocal() as session:
                    worker = RepoManagerWorker(session)
                    await worker.execute(repo_manager_run_id=repo_manager_run_id)
                    logger.info(
                        "Repo manager worker finished run worker_id=%s repo_manager_run_id=%s",
                        worker_id,
                        repo_manager_run_id,
                    )
            except Exception:
                logger.exception(
                    "Repo manager worker %s failed processing run %s",
                    worker_id,
                    repo_manager_run_id,
                )
            finally:
                self._queue.task_done()


_runner: RepoManagerBackgroundRunner | None = None


def get_repo_manager_runner() -> RepoManagerBackgroundRunner:
    """Return singleton repo-manager background runner instance."""

    global _runner
    if _runner is None:
        settings = get_settings()
        _runner = RepoManagerBackgroundRunner(
            max_concurrent_runs=settings.REPO_MANAGER_MAX_CONCURRENT_RUNS,
        )
    return _runner