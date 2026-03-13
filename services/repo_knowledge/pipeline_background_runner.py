from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from config.settings import get_settings
from infrastructure.database import SessionLocal
from services.repo_knowledge.pipeline_service import RepoKnowledgePipelineCoordinator, RepoPipelineQueueItem

logger = logging.getLogger(__name__)


class RepoPipelineBackgroundRunner:
    """In-process async runner that orchestrates multi-stage repo-knowledge pipelines."""

    def __init__(self, *, max_concurrent_runs: int, poll_seconds: int) -> None:
        self.max_concurrent_runs = max(1, max_concurrent_runs)
        self.poll_seconds = max(1, poll_seconds)
        self._queue: asyncio.Queue[RepoPipelineQueueItem] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        """Start pipeline coordinator workers."""
        if self._started:
            logger.debug("Repo pipeline runner start skipped (already started)")
            return
        self._started = True
        logger.info(
            "Repo pipeline runner starting workers=%s poll_seconds=%s",
            self.max_concurrent_runs,
            self.poll_seconds,
        )
        for idx in range(self.max_concurrent_runs):
            task = asyncio.create_task(self._worker_loop(worker_id=idx), name=f"repo-pipeline-worker-{idx}")
            self._workers.append(task)
            logger.info("Repo pipeline worker started worker_id=%s", idx)

    async def stop(self) -> None:
        """Stop workers gracefully."""
        if not self._started:
            logger.debug("Repo pipeline runner stop skipped (not started)")
            return
        logger.info("Repo pipeline runner stopping workers=%s", len(self._workers))
        self._started = False
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            with suppress(asyncio.CancelledError):
                await task
        self._workers.clear()
        logger.info("Repo pipeline runner stopped")

    async def enqueue(self, item: RepoPipelineQueueItem) -> None:
        """Queue one source run pipeline for end-to-end orchestration."""
        await self._queue.put(item)
        logger.info(
            "Repo pipeline run enqueued source_run_id=%s tenant=%s user=%s queue_size=%s",
            item.source_run_id,
            item.tenant_id,
            item.user_id,
            self._queue.qsize(),
        )

    async def _worker_loop(self, *, worker_id: int) -> None:
        while True:
            item = await self._queue.get()
            logger.info(
                "Repo pipeline worker picked source_run_id=%s tenant=%s user=%s worker_id=%s",
                item.source_run_id,
                item.tenant_id,
                item.user_id,
                worker_id,
            )
            try:
                await self._drive_pipeline(item=item, worker_id=worker_id)
            except Exception:
                logger.exception(
                    "Repo pipeline worker failed source_run_id=%s tenant=%s user=%s worker_id=%s",
                    item.source_run_id,
                    item.tenant_id,
                    item.user_id,
                    worker_id,
                )
            finally:
                self._queue.task_done()

    async def _drive_pipeline(self, *, item: RepoPipelineQueueItem, worker_id: int) -> None:
        while True:
            async with SessionLocal() as session:
                coordinator = RepoKnowledgePipelineCoordinator(session, task=item)
                terminal = await coordinator.advance_once()
                await session.commit()

            if terminal:
                logger.info(
                    "Repo pipeline worker finished source_run_id=%s tenant=%s user=%s worker_id=%s",
                    item.source_run_id,
                    item.tenant_id,
                    item.user_id,
                    worker_id,
                )
                return

            await asyncio.sleep(self.poll_seconds)


_runner: RepoPipelineBackgroundRunner | None = None


def get_repo_pipeline_runner() -> RepoPipelineBackgroundRunner:
    """Return singleton repo pipeline runner instance."""
    global _runner
    if _runner is None:
        settings = get_settings()
        _runner = RepoPipelineBackgroundRunner(
            max_concurrent_runs=settings.REPO_PIPELINE_MAX_CONCURRENT_RUNS,
            poll_seconds=settings.REPO_PIPELINE_POLL_SECONDS,
        )
    return _runner

