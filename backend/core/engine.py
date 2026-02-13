"""Experiment execution engine for running and monitoring training processes."""

import asyncio
import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.websocket import manager
from backend.models.experiment import MetricRecord


class ExperimentEngine:
    """Engine for executing and monitoring ML experiments."""

    def __init__(self) -> None:
        """Initialize experiment engine."""
        # experiment_id -> Process
        self.running_processes: dict[int, asyncio.subprocess.Process] = {}
        # experiment_id -> monitoring task
        self.monitoring_tasks: dict[int, asyncio.Task[None]] = {}

    async def start_experiment(
        self,
        experiment_id: int,
        script_path: str,
        hyperparameters: dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Start an experiment by launching the training process."""
        # Build command with hyperparameters
        cmd = ["python", script_path]
        for key, value in hyperparameters.items():
            cmd.extend([f"--{key}", str(value)])

        # Launch subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self.running_processes[experiment_id] = process

        # Start monitoring task
        task = asyncio.create_task(
            self._monitor_process(experiment_id, process, session)
        )
        self.monitoring_tasks[experiment_id] = task

    async def stop_experiment(self, experiment_id: int) -> bool:
        """Stop a running experiment."""
        if experiment_id not in self.running_processes:
            return False

        process = self.running_processes[experiment_id]

        # Try graceful termination first
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # Force kill if termination doesn't work
            process.kill()
            await process.wait()

        # Cancel monitoring task
        if experiment_id in self.monitoring_tasks:
            self.monitoring_tasks[experiment_id].cancel()
            try:
                await self.monitoring_tasks[experiment_id]
            except asyncio.CancelledError:
                pass
            del self.monitoring_tasks[experiment_id]

        del self.running_processes[experiment_id]
        return True

    async def _monitor_process(
        self,
        experiment_id: int,
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
                                experiment_id, metric_data, session
                            )
                    except Exception:
                        # Ignore parsing errors, continue monitoring
                        continue

            # Wait for process to complete
            return_code = await process.wait()

            # Notify completion via WebSocket
            await manager.broadcast(
                experiment_id,
                {
                    "type": "experiment_completed",
                    "experiment_id": experiment_id,
                    "return_code": return_code,
                },
            )
        except asyncio.CancelledError:
            # Monitoring was cancelled
            pass
        except Exception:
            # Notify error via WebSocket
            await manager.broadcast(
                experiment_id,
                {
                    "type": "experiment_error",
                    "experiment_id": experiment_id,
                },
            )
        finally:
            # Cleanup
            if experiment_id in self.running_processes:
                del self.running_processes[experiment_id]
            if experiment_id in self.monitoring_tasks:
                del self.monitoring_tasks[experiment_id]

    async def _process_metric(
        self,
        experiment_id: int,
        metric_data: dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Process and store a parsed metric."""
        step = metric_data.get("step")
        if step is None:
            return

        # Extract all numeric metrics (excluding 'step')
        for name, value in metric_data.items():
            if name == "step":
                continue
            if not isinstance(value, (int, float)):
                continue

            # Save to database
            metric_record = MetricRecord(
                experiment_id=experiment_id,
                step=step,
                name=name,
                value=float(value),
                timestamp=datetime.utcnow(),
            )
            session.add(metric_record)

        await session.commit()

        # Broadcast to WebSocket clients
        await manager.broadcast(
            experiment_id,
            {
                "type": "metric",
                "experiment_id": experiment_id,
                "step": step,
                "metrics": {
                    k: v
                    for k, v in metric_data.items()
                    if k != "step" and isinstance(v, (int, float))
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


# Global engine instance
engine = ExperimentEngine()
