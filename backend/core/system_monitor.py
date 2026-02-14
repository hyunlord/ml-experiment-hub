"""Background system stats collector for active training runs.

Periodically polls GPU/CPU/RAM utilization and writes to SystemStats table.
Broadcasts updates via WebSocket to connected dashboard clients.
"""

import asyncio
import logging
import shutil
from datetime import datetime
from typing import Any

from sqlmodel import select

from backend.api.websocket import manager
from backend.models.database import async_session_maker
from backend.models.experiment import ExperimentRun, SystemStats
from shared.schemas import RunStatus

logger = logging.getLogger(__name__)

# Collection interval in seconds
COLLECT_INTERVAL = 2.0


class SystemMonitorService:
    """Collects system stats for running experiments.

    Runs as a background asyncio task. When active runs exist,
    polls GPU/CPU/RAM every COLLECT_INTERVAL seconds and writes
    to SystemStats table + broadcasts via WebSocket.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        """Start the background monitor loop."""
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("SystemMonitorService started")

    def stop(self) -> None:
        """Stop the background monitor loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("SystemMonitorService stopped")

    async def _loop(self) -> None:
        """Main loop: check for active runs and collect stats."""
        while self._running:
            try:
                async with async_session_maker() as session:
                    # Find all running experiments
                    result = await session.execute(
                        select(ExperimentRun).where(ExperimentRun.status == RunStatus.RUNNING)
                    )
                    active_runs = result.scalars().all()

                    if active_runs:
                        stats = await self._collect_stats()
                        if stats:
                            for run in active_runs:
                                await self._record_stats(
                                    run.id,
                                    stats,
                                    session,
                                )
                            await session.commit()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("SystemMonitorService error")

            await asyncio.sleep(COLLECT_INTERVAL)

    async def _collect_stats(self) -> dict[str, Any] | None:
        """Collect current GPU/CPU/RAM utilization."""
        stats: dict[str, Any] = {}

        # CPU percent (using /proc/stat or psutil-like approach)
        try:
            stats["cpu_percent"] = await self._get_cpu_percent()
        except Exception:
            stats["cpu_percent"] = None

        # RAM percent
        try:
            stats["ram_percent"] = await self._get_ram_percent()
        except Exception:
            stats["ram_percent"] = None

        # GPU stats via nvidia-smi
        try:
            gpu_stats = await self._get_gpu_stats()
            if gpu_stats:
                stats["gpu_util"] = gpu_stats.get("gpu_util")
                stats["gpu_memory_used"] = gpu_stats.get("gpu_memory_used")
                stats["gpu_memory_total"] = gpu_stats.get("gpu_memory_total")
                stats["gpus"] = gpu_stats.get("gpus")
        except Exception:
            pass

        return stats if any(v is not None for k, v in stats.items() if k != "gpus") else None

    async def _get_cpu_percent(self) -> float | None:
        """Get CPU utilization percentage."""
        try:
            # Use top command for quick CPU snapshot (macOS & Linux compatible)
            proc = await asyncio.create_subprocess_exec(
                "python",
                "-c",
                "import psutil; print(psutil.cpu_percent(interval=0.1))",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            return float(stdout.decode().strip())
        except Exception:
            return None

    async def _get_ram_percent(self) -> float | None:
        """Get RAM utilization percentage."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "python",
                "-c",
                "import psutil; print(psutil.virtual_memory().percent)",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            return float(stdout.decode().strip())
        except Exception:
            return None

    async def _get_gpu_stats(self) -> dict[str, Any] | None:
        """Get GPU stats via nvidia-smi."""
        if not shutil.which("nvidia-smi"):
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            lines = stdout.decode().strip().split("\n")

            gpus = []
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpus.append(
                        {
                            "index": int(parts[0]),
                            "name": parts[1],
                            "util": float(parts[2]),
                            "memory_used_mb": float(parts[3]),
                            "memory_total_mb": float(parts[4]),
                            "memory_percent": round(float(parts[3]) / float(parts[4]) * 100, 1)
                            if float(parts[4]) > 0
                            else 0,
                            "temperature": float(parts[5])
                            if len(parts) > 5 and parts[5] != "N/A"
                            else None,
                        }
                    )

            if not gpus:
                return None

            # Primary GPU stats (GPU 0)
            primary = gpus[0]
            return {
                "gpu_util": primary["util"],
                "gpu_memory_used": primary["memory_used_mb"],
                "gpu_memory_total": primary["memory_total_mb"],
                "gpus": gpus,
            }
        except Exception:
            return None

    async def _record_stats(
        self,
        run_id: int,
        stats: dict[str, Any],
        session: Any,
    ) -> None:
        """Write stats to DB and broadcast via WebSocket."""
        stat = SystemStats(
            run_id=run_id,
            timestamp=datetime.utcnow(),
            gpu_util=stats.get("gpu_util"),
            gpu_memory_used=stats.get("gpu_memory_used"),
            gpu_memory_total=stats.get("gpu_memory_total"),
            cpu_percent=stats.get("cpu_percent"),
            ram_percent=stats.get("ram_percent"),
        )
        session.add(stat)

        # Check GPU temperatures for warnings
        gpu_warnings: list[dict[str, Any]] = []
        if stats.get("gpus"):
            from backend.services.health_checks import check_gpu_temperatures

            gpu_warnings = check_gpu_temperatures(stats["gpus"])
            for w in gpu_warnings:
                logger.warning("GPU temp alert for run %d: %s", run_id, w["message"])

        # Broadcast to WebSocket
        ws_data: dict[str, Any] = {
            "type": "system_stats",
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "gpu_util": stats.get("gpu_util"),
            "gpu_memory_used": stats.get("gpu_memory_used"),
            "gpu_memory_total": stats.get("gpu_memory_total"),
            "cpu_percent": stats.get("cpu_percent"),
            "ram_percent": stats.get("ram_percent"),
        }
        if stats.get("gpus"):
            ws_data["gpus"] = stats["gpus"]
        if gpu_warnings:
            ws_data["gpu_warnings"] = gpu_warnings

        await manager.broadcast(run_id, ws_data, channel="system")


# Global instance
system_monitor = SystemMonitorService()
