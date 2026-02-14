"""Queue scheduler — polls every 5 seconds and auto-starts next queued experiment.

Checks how many runs are currently active. If fewer than max_concurrent_runs,
picks the next WAITING queue entry (by position) and starts it.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlmodel import select

from backend.models.database import async_session_maker
from backend.models.experiment import ExperimentRun, QueueEntry
from shared.schemas import QueueStatus, RunStatus

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds


class QueueScheduler:
    """Background scheduler that auto-starts queued experiments."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        """Start the scheduler background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Queue scheduler started (poll interval: %ds)", POLL_INTERVAL)

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Queue scheduler stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Queue scheduler tick error")
            await asyncio.sleep(POLL_INTERVAL)

    async def _tick(self) -> None:
        """Single scheduler tick — check capacity and start next."""
        from backend.services.notifier import get_hub_settings

        hub_settings = get_hub_settings()
        max_concurrent = hub_settings.get("max_concurrent_runs", 1)

        async with async_session_maker() as session:
            # Count currently running experiments
            result = await session.execute(
                select(ExperimentRun).where(ExperimentRun.status == RunStatus.RUNNING)
            )
            running_runs = list(result.scalars().all())
            running_count = len(running_runs)

            # Also count RUNNING queue entries (may not have started yet)
            result = await session.execute(
                select(QueueEntry).where(QueueEntry.status == QueueStatus.RUNNING)
            )
            running_queue = list(result.scalars().all())

            # Reconcile: check if running queue entries' runs have finished
            for qe in running_queue:
                if qe.run_id:
                    run_result = await session.execute(
                        select(ExperimentRun).where(ExperimentRun.id == qe.run_id)
                    )
                    run = run_result.scalar_one_or_none()
                    if run and run.status == RunStatus.COMPLETED:
                        qe.status = QueueStatus.COMPLETED
                        qe.completed_at = datetime.utcnow()
                        await session.commit()
                    elif run and run.status == RunStatus.FAILED:
                        qe.status = QueueStatus.FAILED
                        qe.completed_at = datetime.utcnow()
                        qe.error_message = "Run failed"
                        await session.commit()
                    elif run and run.status == RunStatus.CANCELLED:
                        qe.status = QueueStatus.CANCELLED
                        qe.completed_at = datetime.utcnow()
                        await session.commit()

            if running_count >= max_concurrent:
                return  # At capacity

            # How many slots are free?
            free_slots = max_concurrent - running_count

            # Get next waiting entries
            result = await session.execute(
                select(QueueEntry)
                .where(QueueEntry.status == QueueStatus.WAITING)
                .order_by(QueueEntry.position)
                .limit(free_slots)
            )
            waiting = list(result.scalars().all())

            if not waiting:
                return

            for entry in waiting:
                await self._start_entry(entry, session)

    async def _start_entry(self, entry: QueueEntry, session: object) -> None:
        """Start a single queue entry."""
        from backend.core.process_manager import runner

        logger.info(
            "Queue: starting experiment %d (queue entry %d, position %d)",
            entry.experiment_config_id,
            entry.id,
            entry.position,
        )

        try:
            run = await runner.start(entry.experiment_config_id, session)  # type: ignore[arg-type]
            entry.status = QueueStatus.RUNNING
            entry.run_id = run.id
            entry.started_at = datetime.utcnow()
            await session.commit()  # type: ignore[union-attr]

            logger.info(
                "Queue: experiment %d started as run %d",
                entry.experiment_config_id,
                run.id,
            )
        except Exception as e:
            logger.error(
                "Queue: failed to start experiment %d: %s",
                entry.experiment_config_id,
                e,
            )
            entry.status = QueueStatus.FAILED
            entry.error_message = str(e)
            entry.completed_at = datetime.utcnow()
            await session.commit()  # type: ignore[union-attr]


# Global instance
queue_scheduler = QueueScheduler()
