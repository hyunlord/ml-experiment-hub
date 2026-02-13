"""Experiment execution engine for running and monitoring training processes."""

import asyncio
import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.websocket import manager
from backend.models.experiment import MetricLog


class ExperimentEngine:
    """Engine for executing and monitoring ML experiments."""

    def __init__(self) -> None:
        """Initialize experiment engine."""
        # run_id -> Process
        self.running_processes: dict[int, asyncio.subprocess.Process] = {}
        # run_id -> monitoring task
        self.monitoring_tasks: dict[int, asyncio.Task[None]] = {}

    async def start_experiment(
        self,
        run_id: int,
        script_path: str,
        config_json: dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Start an experiment run by launching the training process."""
        # Build command with config parameters
        cmd = ["python", script_path]
        for key, value in config_json.items():
            cmd.extend([f"--{key}", str(value)])

        # Launch subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self.running_processes[run_id] = process

        # Start monitoring task
        task = asyncio.create_task(
            self._monitor_process(run_id, process, session)
        )
        self.monitoring_tasks[run_id] = task

    async def stop_experiment(self, run_id: int) -> bool:
        """Stop a running experiment."""
        if run_id not in self.running_processes:
            return False

        process = self.running_processes[run_id]

        # Try graceful termination first
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # Force kill if termination doesn't work
            process.kill()
            await process.wait()

        # Cancel monitoring task
        if run_id in self.monitoring_tasks:
            self.monitoring_tasks[run_id].cancel()
            try:
                await self.monitoring_tasks[run_id]
            except asyncio.CancelledError:
                pass
            del self.monitoring_tasks[run_id]

        del self.running_processes[run_id]
        return True

    async def _monitor_process(
        self,
        run_id: int,
        process: asyncio.subprocess.Process,
        session: AsyncSession,
    ) -> None:
        """Monitor process output and parse metrics."""
        try:
            # Pattern to match metric lines: {"step": 100, "loss": 0.5, "accuracy": 0.95}
            metric_pattern = re.compile(r'\{.*"step".*:.*\d+.*\}')

            if process.stdout:
                async for line in process.stdout:
                    try:
                        line_str = line.decode().strip()

                        # Try to parse as JSON metric
                        match = metric_pattern.search(line_str)
                        if match:
                            metric_data = json.loads(match.group())
                            await self._process_metric(
                                run_id, metric_data, session
                            )
                    except Exception:
                        # Ignore parsing errors, continue monitoring
                        continue

            # Wait for process to complete
            return_code = await process.wait()

            # Notify completion via WebSocket
            await manager.broadcast(
                run_id,
                {
                    "type": "run_completed",
                    "run_id": run_id,
                    "return_code": return_code,
                },
            )
        except asyncio.CancelledError:
            # Monitoring was cancelled
            pass
        except Exception:
            # Notify error via WebSocket
            await manager.broadcast(
                run_id,
                {
                    "type": "run_error",
                    "run_id": run_id,
                },
            )
        finally:
            # Cleanup
            if run_id in self.running_processes:
                del self.running_processes[run_id]
            if run_id in self.monitoring_tasks:
                del self.monitoring_tasks[run_id]

    async def _process_metric(
        self,
        run_id: int,
        metric_data: dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Process and store a parsed metric."""
        step = metric_data.get("step")
        epoch = metric_data.get("epoch")

        if step is None:
            return

        # Extract all metrics (excluding 'step' and 'epoch')
        metrics_json = {
            k: v
            for k, v in metric_data.items()
            if k not in ("step", "epoch")
        }

        if not metrics_json:
            return

        # Save to database as single MetricLog entry
        metric_log = MetricLog(
            run_id=run_id,
            step=step,
            epoch=epoch,
            metrics_json=metrics_json,
            timestamp=datetime.utcnow(),
        )
        session.add(metric_log)
        await session.commit()

        # Broadcast to WebSocket clients
        await manager.broadcast(
            run_id,
            {
                "type": "metric",
                "run_id": run_id,
                "step": step,
                "epoch": epoch,
                "metrics": metrics_json,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


# Global engine instance
engine = ExperimentEngine()
