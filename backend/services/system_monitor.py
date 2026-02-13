"""System resource monitor for GPU/CPU/RAM collection during training runs.

Collects hardware metrics at configurable intervals, broadcasts via
WebSocket for real-time UI updates, and persists to DB at a lower
frequency to avoid excessive storage.
"""

import asyncio
import logging
import shutil
from datetime import datetime
from typing import Any

import psutil

from backend.api.websocket import manager as ws_manager
from backend.models.database import async_session_maker
from backend.models.experiment import SystemStats

logger = logging.getLogger(__name__)

# Try to import pynvml for GPU monitoring
_nvml_available = False
try:
    import pynvml  # provided by nvidia-ml-py

    pynvml.nvmlInit()
    _nvml_available = True
except Exception:
    logger.info("NVML not available — GPU monitoring disabled")


class SystemMonitor:
    """Async system resource monitor with WebSocket broadcast and DB persistence.

    Usage:
        monitor = SystemMonitor()
        await monitor.start_monitoring(run_id, interval=1.0)
        ...
        await monitor.stop_monitoring(run_id)
    """

    def __init__(self) -> None:
        """Initialize the system monitor."""
        # run_id -> monitoring task
        self._tasks: dict[int, asyncio.Task[None]] = {}

    async def collect(self) -> dict[str, Any]:
        """Collect a snapshot of all system resources.

        Returns:
            {
                "timestamp": "...",
                "gpus": [{"index": 0, "name": "...", "util": 85, ...}],
                "cpu": {"percent": 45, "count": 20},
                "ram": {"used_gb": 32.1, "total_gb": 128.0, "percent": 25.1},
                "disk": {"used_gb": 100, "total_gb": 500},
            }
        """
        snapshot: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
        }

        # GPU metrics via pynvml
        snapshot["gpus"] = _collect_gpu_stats()

        # CPU metrics via psutil
        snapshot["cpu"] = {
            "percent": psutil.cpu_percent(interval=None),
            "count": psutil.cpu_count(logical=True),
        }

        # RAM metrics via psutil
        mem = psutil.virtual_memory()
        snapshot["ram"] = {
            "used_gb": round(mem.used / (1024**3), 2),
            "total_gb": round(mem.total / (1024**3), 2),
            "percent": mem.percent,
        }

        # Disk metrics
        disk = shutil.disk_usage("/")
        snapshot["disk"] = {
            "used_gb": round(disk.used / (1024**3), 1),
            "total_gb": round(disk.total / (1024**3), 1),
        }

        return snapshot

    async def start_monitoring(
        self, run_id: int, interval: float = 1.0
    ) -> None:
        """Start background monitoring for a run.

        Args:
            run_id: The ExperimentRun ID to monitor.
            interval: Seconds between collections (default: 1s).
        """
        if run_id in self._tasks:
            logger.warning("Monitoring already active for run %d", run_id)
            return

        task = asyncio.create_task(self._monitor_loop(run_id, interval))
        self._tasks[run_id] = task
        logger.info("Started system monitoring for run %d (interval=%.1fs)", run_id, interval)

    async def stop_monitoring(self, run_id: int) -> None:
        """Stop background monitoring for a run."""
        task = self._tasks.pop(run_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped system monitoring for run %d", run_id)

    def is_monitoring(self, run_id: int) -> bool:
        """Check if monitoring is active for a run."""
        return run_id in self._tasks

    async def _monitor_loop(self, run_id: int, interval: float) -> None:
        """Background loop: collect → broadcast → periodic DB save."""
        tick = 0
        db_save_every = max(1, int(10.0 / interval))  # Save to DB every ~10 seconds

        try:
            while True:
                snapshot = await self.collect()

                # Broadcast to WebSocket clients every tick
                await ws_manager.broadcast(
                    run_id,
                    {"type": "system_stats", "run_id": run_id, **snapshot},
                    channel="system",
                )

                # Persist to DB at lower frequency
                if tick % db_save_every == 0:
                    await self._persist(run_id, snapshot)

                tick += 1
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            # Final snapshot on stop
            try:
                snapshot = await self.collect()
                await self._persist(run_id, snapshot)
            except Exception:
                pass
            raise

    async def _persist(self, run_id: int, snapshot: dict[str, Any]) -> None:
        """Save a system stats snapshot to the database."""
        try:
            # Use first GPU's stats for the SystemStats table
            # (the full multi-GPU data goes via WebSocket)
            gpu = snapshot["gpus"][0] if snapshot["gpus"] else {}

            stats = SystemStats(
                run_id=run_id,
                timestamp=datetime.utcnow(),
                gpu_util=gpu.get("util"),
                gpu_memory_used=gpu.get("memory_used_mb"),
                gpu_memory_total=gpu.get("memory_total_mb"),
                cpu_percent=snapshot["cpu"]["percent"],
                ram_percent=snapshot["ram"]["percent"],
            )

            async with async_session_maker() as session:
                session.add(stats)
                await session.commit()

        except Exception:
            logger.exception("Failed to persist system stats for run %d", run_id)


def _collect_gpu_stats() -> list[dict[str, Any]]:
    """Collect GPU stats via pynvml. Returns empty list if unavailable."""
    if not _nvml_available:
        return []

    gpus: list[dict[str, Any]] = []
    try:
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

            try:
                temp = pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU
                )
            except Exception:
                temp = None

            gpus.append({
                "index": i,
                "name": name,
                "util": util.gpu,
                "memory_used_mb": round(mem_info.used / (1024**2), 1),
                "memory_total_mb": round(mem_info.total / (1024**2), 1),
                "memory_percent": round(mem_info.used / mem_info.total * 100, 1)
                if mem_info.total > 0
                else 0,
                "temperature": temp,
            })
    except Exception:
        logger.debug("GPU stats collection failed", exc_info=True)

    return gpus


# Global monitor instance
system_monitor = SystemMonitor()
