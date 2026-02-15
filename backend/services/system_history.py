"""Background system history collector and query service.

Periodically snapshots system stats to SystemHistorySnapshot table
for time-series history charts. Handles downsampling of old data.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlmodel import col, select

from backend.models.database import async_session_maker
from backend.models.experiment import SystemHistorySnapshot

logger = logging.getLogger(__name__)

# Collection interval in seconds
HISTORY_COLLECT_INTERVAL = 10.0

# Downsampling: keep raw data for 24h, then 1-min intervals
DOWNSAMPLE_AGE_HOURS = 24
DOWNSAMPLE_INTERVAL_SECONDS = 60
DOWNSAMPLE_RUN_INTERVAL = 3600  # Run downsample check every hour


class SystemHistoryService:
    """Collects global system stats snapshots for history charts.

    Runs as a background asyncio task independently of training runs.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._last_downsample = 0.0

    def start(self) -> None:
        """Start the background history collection loop."""
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("SystemHistoryService started (interval=%ss)", HISTORY_COLLECT_INTERVAL)

    def stop(self) -> None:
        """Stop the background history collection loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("SystemHistoryService stopped")

    async def _loop(self) -> None:
        """Main loop: collect snapshot and periodically downsample."""
        import time

        while self._running:
            try:
                await self._collect_snapshot()

                # Run downsample periodically
                now = time.monotonic()
                if now - self._last_downsample > DOWNSAMPLE_RUN_INTERVAL:
                    await self._downsample_old_data()
                    self._last_downsample = now

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("SystemHistoryService error")

            await asyncio.sleep(HISTORY_COLLECT_INTERVAL)

    async def _collect_snapshot(self) -> None:
        """Collect a single system stats snapshot and write to DB."""
        from backend.services.system_info import collect_system_info

        try:
            stats = await collect_system_info()
        except Exception:
            logger.debug("Failed to collect system info for history", exc_info=True)
            return

        # Extract summary metrics for the snapshot
        gpu_util = None
        gpu_mem_pct = None
        gpu_temp = None

        gpus = stats.get("gpus", [])
        if gpus:
            # Use primary GPU (index 0)
            gpu_util = gpus[0].get("util")
            gpu_mem_pct = gpus[0].get("memory_percent")
            gpu_temp = gpus[0].get("temperature")

        cpu = stats.get("cpu", {})
        ram = stats.get("ram", {})
        disk = stats.get("disk", {})

        # For disk percent, use the root partition
        disk_pct = None
        partitions = disk.get("partitions", [])
        if partitions:
            root = next((p for p in partitions if p["mountpoint"] == "/"), partitions[0])
            disk_pct = root.get("percent")

        snapshot = SystemHistorySnapshot(
            timestamp=datetime.utcnow(),
            server_id=None,  # Local server
            gpu_util=gpu_util,
            gpu_memory_percent=gpu_mem_pct,
            gpu_temperature=gpu_temp,
            cpu_percent=cpu.get("percent"),
            ram_percent=ram.get("percent"),
            disk_percent=disk_pct,
        )

        async with async_session_maker() as session:
            session.add(snapshot)
            await session.commit()

    async def _downsample_old_data(self) -> None:
        """Downsample data older than DOWNSAMPLE_AGE_HOURS.

        Keeps one point per DOWNSAMPLE_INTERVAL_SECONDS by deleting
        excess rows in each interval bucket.
        """
        cutoff = datetime.utcnow() - timedelta(hours=DOWNSAMPLE_AGE_HOURS)

        async with async_session_maker() as session:
            # Get all old snapshots ordered by timestamp
            result = await session.execute(
                select(SystemHistorySnapshot)
                .where(col(SystemHistorySnapshot.timestamp) < cutoff)
                .order_by(SystemHistorySnapshot.timestamp)
            )
            old_snapshots = result.scalars().all()

            if len(old_snapshots) < 10:
                return  # Not enough data to downsample

            # Group into buckets and keep first of each bucket
            ids_to_delete: list[int] = []
            current_bucket_start: datetime | None = None

            for snap in old_snapshots:
                bucket_start = snap.timestamp.replace(
                    second=(snap.timestamp.second // DOWNSAMPLE_INTERVAL_SECONDS)
                    * DOWNSAMPLE_INTERVAL_SECONDS,
                    microsecond=0,
                )
                if current_bucket_start is None or bucket_start != current_bucket_start:
                    # First point in new bucket — keep it
                    current_bucket_start = bucket_start
                else:
                    # Duplicate in same bucket — mark for deletion
                    if snap.id is not None:
                        ids_to_delete.append(snap.id)

            if ids_to_delete:
                # Delete in batches
                for i in range(0, len(ids_to_delete), 500):
                    batch = ids_to_delete[i : i + 500]
                    await session.execute(
                        delete(SystemHistorySnapshot).where(
                            col(SystemHistorySnapshot.id).in_(batch)
                        )
                    )
                await session.commit()
                logger.info(
                    "Downsampled system history: deleted %d old snapshots",
                    len(ids_to_delete),
                )


# Global instance
system_history_service = SystemHistoryService()


# ---------------------------------------------------------------------------
# Query helpers (used by API)
# ---------------------------------------------------------------------------


async def get_system_history(
    range_hours: int = 1,
    server_id: int | None = None,
) -> list[dict[str, Any]]:
    """Query system history for the given time range.

    Args:
        range_hours: How many hours of history to return (1, 6, or 24).
        server_id: Filter by server (None = local).

    Returns:
        List of snapshot dicts ordered by timestamp.
    """
    since = datetime.utcnow() - timedelta(hours=range_hours)

    async with async_session_maker() as session:
        query = (
            select(SystemHistorySnapshot)
            .where(col(SystemHistorySnapshot.timestamp) >= since)
            .order_by(SystemHistorySnapshot.timestamp)
        )
        if server_id is not None:
            query = query.where(SystemHistorySnapshot.server_id == server_id)
        else:
            query = query.where(SystemHistorySnapshot.server_id.is_(None))  # type: ignore[union-attr]

        result = await session.execute(query)
        snapshots = result.scalars().all()

    return [
        {
            "timestamp": s.timestamp.isoformat(),
            "gpu_util": s.gpu_util,
            "gpu_memory_percent": s.gpu_memory_percent,
            "gpu_temperature": s.gpu_temperature,
            "cpu_percent": s.cpu_percent,
            "ram_percent": s.ram_percent,
            "disk_percent": s.disk_percent,
        }
        for s in snapshots
    ]
