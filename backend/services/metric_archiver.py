"""Metric archival service.

Archives detailed MetricLog entries for completed runs older than a
configurable threshold, keeping only the summary in ExperimentRun.metrics_summary.

This prevents the metric_logs table from growing unboundedly for long-lived
deployments with many completed experiments.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, func, select

from backend.models.experiment import ExperimentRun, MetricLog
from shared.schemas import RunStatus

logger = logging.getLogger(__name__)

# Only archive metrics for runs completed more than this many days ago
ARCHIVE_AFTER_DAYS = 14

# Completed statuses eligible for archival
_ARCHIVABLE = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}


async def archive_old_metrics(
    session: AsyncSession,
    days: int = ARCHIVE_AFTER_DAYS,
) -> int:
    """Delete detailed MetricLog rows for old completed runs.

    Precondition: ExperimentRun.metrics_summary must already contain
    the aggregated final metrics (populated by process_manager on completion).

    Returns:
        Number of MetricLog rows deleted.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Find completed runs with ended_at before cutoff that still have metric logs
    subq = select(ExperimentRun.id).where(
        ExperimentRun.status.in_([s.value for s in _ARCHIVABLE]),  # type: ignore[union-attr]
        ExperimentRun.ended_at.is_not(None),  # type: ignore[union-attr]
        ExperimentRun.ended_at < cutoff,  # type: ignore[operator]
    )

    # Count before delete
    count_q = select(func.count()).select_from(MetricLog).where(MetricLog.run_id.in_(subq))  # type: ignore[union-attr]
    result = await session.execute(count_q)
    count = result.scalar() or 0

    if count == 0:
        return 0

    # Delete the rows
    stmt = delete(MetricLog).where(MetricLog.run_id.in_(subq))  # type: ignore[union-attr]
    await session.execute(stmt)
    await session.commit()

    logger.info("Archived %d metric log rows for runs completed before %s", count, cutoff.date())
    return count
