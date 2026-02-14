"""Process manager for ML training subprocess lifecycle.

Manages the full lifecycle of training processes: start, stop, monitor,
and cleanup. Each experiment run is launched as a separate Python subprocess
with its config written to a temporary YAML file.
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from adapters import get_adapter
from adapters.base import BaseAdapter
from backend.api.websocket import manager as ws_manager
from backend.config import settings
from backend.core.env_manager import env_manager
from backend.models.experiment import ExperimentConfig, ExperimentRun, MetricLog
from shared.schemas import ExperimentConfigStatus, RunStatus
from shared.utils import unflatten_dict

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Manages ML training processes as system subprocesses.

    The runner is responsible for:
    - Converting experiment configs to YAML and launching training
    - Monitoring stdout for metrics and persisting them
    - Gracefully stopping processes (SIGTERM -> SIGKILL)
    - Cleaning up zombie processes and temp files
    """

    def __init__(self) -> None:
        """Initialize the experiment runner."""
        # run_id -> subprocess
        self._processes: dict[int, asyncio.subprocess.Process] = {}
        # run_id -> monitoring task
        self._monitors: dict[int, asyncio.Task[None]] = {}
        # run_id -> adapter
        self._adapters: dict[int, BaseAdapter] = {}
        # run_id -> temp yaml path
        self._config_files: dict[int, str] = {}

        # Ensure log directory exists
        self._log_dir = Path(settings.LOG_DIR)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Config YAML output directory (empty = system tempdir)
        self._config_dir = Path(settings.CONFIG_DIR) if settings.CONFIG_DIR else None
        if self._config_dir:
            self._config_dir.mkdir(parents=True, exist_ok=True)

    async def start(
        self,
        experiment_id: int,
        session: AsyncSession,
        adapter_name: str = "pytorch_lightning",
    ) -> ExperimentRun:
        """Start a training process for an experiment.

        1. Load the experiment config
        2. Convert dot-notation config → nested dict → YAML file
        3. Create an ExperimentRun record
        4. Launch subprocess with stdout/stderr → log file
        5. Start background monitoring for metrics

        Args:
            experiment_id: ID of the ExperimentConfig to run.
            session: Database session.
            adapter_name: Which adapter to use (default: pytorch_lightning).

        Returns:
            The created ExperimentRun.

        Raises:
            ValueError: If experiment not found or not in runnable state.
        """
        # Load experiment config
        result = await session.execute(
            select(ExperimentConfig).where(ExperimentConfig.id == experiment_id)
        )
        experiment = result.scalar_one_or_none()
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        if experiment.status not in (
            ExperimentConfigStatus.DRAFT,
            ExperimentConfigStatus.QUEUED,
        ):
            raise ValueError(
                f"Experiment {experiment_id} is in '{experiment.status.value}' state, "
                "must be DRAFT or QUEUED to start"
            )

        # Get adapter
        adapter = get_adapter(adapter_name)

        # Set up project venv (creates/updates if needed)
        project_dir = str(Path(settings.PROJECTS_DIR))
        try:
            await env_manager.setup_project(project_dir)
        except FileNotFoundError:
            logger.warning(
                "No dependency files found for project at %s, using system Python",
                project_dir,
            )
        except RuntimeError as e:
            raise ValueError(f"Failed to set up project environment: {e}") from e

        # Create ExperimentRun record FIRST (need run.id for monitor config)
        run = ExperimentRun(
            experiment_config_id=experiment_id,
            status=RunStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        session.add(run)

        # Update experiment status
        experiment.status = ExperimentConfigStatus.RUNNING
        experiment.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(run)

        # Convert flat dot-notation config → nested dict
        nested_config = unflatten_dict(experiment.config_json or {})

        # Inject monitor config so MonitorCallback reports to hub
        if hasattr(adapter, "inject_monitor_config"):
            nested_config = adapter.inject_monitor_config(
                nested_config, run_id=run.id, server_url="http://localhost:8000"
            )

        yaml_content = adapter.config_to_yaml(nested_config)

        # Write temp YAML config file
        config_fd, config_path = tempfile.mkstemp(
            prefix=f"exp_{experiment_id}_",
            suffix=".yaml",
            dir=str(self._config_dir) if self._config_dir else None,
        )
        with os.fdopen(config_fd, "w") as f:
            f.write(yaml_content)

        # Set up log file
        log_path = self._log_dir / f"run_{run.id}.log"
        log_file = open(log_path, "w")  # noqa: SIM115

        # Build and launch training command
        cmd = adapter.get_train_command(config_path)

        # Use project venv Python if available
        project_dir = str(Path(settings.PROJECTS_DIR))
        if env_manager.is_ready(project_dir) and cmd and cmd[0] == "python":
            cmd[0] = env_manager.get_python(project_dir)

        logger.info("Starting run %d: %s", run.id, " ".join(cmd))

        # Environment variables for the training subprocess
        env = os.environ.copy()
        env["MONITOR_RUN_ID"] = str(run.id)
        env["MONITOR_SERVER_URL"] = "http://localhost:8000"

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=log_file,
                cwd=settings.PROJECTS_DIR,
                env=env,
            )
        except Exception as e:
            # Cleanup on launch failure
            log_file.close()
            os.unlink(config_path)
            run.status = RunStatus.FAILED
            run.ended_at = datetime.utcnow()
            await session.commit()
            raise ValueError(f"Failed to launch process: {e}") from e

        # Record PID and log path
        run.pid = process.pid
        run.log_path = str(log_path)
        await session.commit()

        # Track state
        self._processes[run.id] = process
        self._adapters[run.id] = adapter
        self._config_files[run.id] = config_path

        # Start background monitoring
        monitor = asyncio.create_task(self._monitor(run.id, process, adapter, log_file, session))
        self._monitors[run.id] = monitor

        # Send start notification
        try:
            from backend.services.notifier import notify_run_started

            await notify_run_started(experiment.name, run.id)  # type: ignore[arg-type]
        except Exception:
            logger.warning("Failed to send start notification for run %d", run.id)

        return run

    async def stop(self, run_id: int, session: AsyncSession) -> bool:
        """Stop a running training process.

        Sends SIGTERM, waits 5 seconds, then SIGKILL if still alive.

        Args:
            run_id: ID of the ExperimentRun to stop.
            session: Database session.

        Returns:
            True if process was stopped, False if not found.
        """
        process = self._processes.get(run_id)
        if not process:
            return False

        logger.info("Stopping run %d (PID %d)", run_id, process.pid or 0)

        # SIGTERM → wait → SIGKILL
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Run %d did not terminate gracefully, sending SIGKILL", run_id)
            process.kill()
            await process.wait()

        # Cancel monitor
        if run_id in self._monitors:
            self._monitors[run_id].cancel()
            try:
                await self._monitors[run_id]
            except asyncio.CancelledError:
                pass

        # Update DB
        result = await session.execute(select(ExperimentRun).where(ExperimentRun.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            run.status = RunStatus.CANCELLED
            run.ended_at = datetime.utcnow()
            await session.commit()

        self._cleanup_run(run_id)
        return True

    async def status(self, run_id: int) -> str:
        """Check if a process is still running.

        Returns:
            'running' if the process is alive, 'dead' otherwise.
        """
        process = self._processes.get(run_id)
        if not process:
            return "dead"
        return "running" if process.returncode is None else "dead"

    def list_active(self) -> list[int]:
        """Return run IDs of all currently active processes."""
        return [run_id for run_id, proc in self._processes.items() if proc.returncode is None]

    async def cleanup(self, session: AsyncSession) -> int:
        """Clean up zombie processes and stale state.

        Finds runs that are tracked but whose process has exited,
        updates their DB status, and removes tracking state.

        Returns:
            Number of zombie processes cleaned up.
        """
        cleaned = 0
        dead_runs = []

        for run_id, process in self._processes.items():
            if process.returncode is not None:
                dead_runs.append(run_id)

        for run_id in dead_runs:
            result = await session.execute(select(ExperimentRun).where(ExperimentRun.id == run_id))
            run = result.scalar_one_or_none()
            if run and run.status == RunStatus.RUNNING:
                return_code = self._processes[run_id].returncode
                run.status = RunStatus.FAILED if return_code != 0 else RunStatus.COMPLETED
                run.ended_at = datetime.utcnow()
                cleaned += 1

            self._cleanup_run(run_id)

        if cleaned:
            await session.commit()

        logger.info("Cleaned up %d zombie processes", cleaned)
        return cleaned

    async def _monitor(
        self,
        run_id: int,
        process: asyncio.subprocess.Process,
        adapter: BaseAdapter,
        log_file: Any,
        session: AsyncSession,
    ) -> None:
        """Monitor process stdout, parse metrics, and handle completion."""
        try:
            if process.stdout:
                async for raw_line in process.stdout:
                    line = raw_line.decode(errors="replace").strip()

                    # Write to log file
                    log_file.write(line + "\n")
                    log_file.flush()

                    # Try to parse metrics via adapter
                    metrics = adapter.parse_metrics(line)
                    if metrics and "step" in metrics:
                        await self._record_metric(run_id, metrics, session)

            # Wait for exit
            return_code = await process.wait()

            # Update run status
            result = await session.execute(select(ExperimentRun).where(ExperimentRun.id == run_id))
            run = result.scalar_one_or_none()
            if run and run.status == RunStatus.RUNNING:
                run.status = RunStatus.COMPLETED if return_code == 0 else RunStatus.FAILED
                run.ended_at = datetime.utcnow()

                # Auto-collect final metrics summary
                await self._collect_final_metrics(run, session)

                await session.commit()

                # Send notifications
                await self._send_run_notification(run, session)

            # Notify via WebSocket
            await ws_manager.broadcast(
                run_id,
                {
                    "type": "run_completed",
                    "run_id": run_id,
                    "return_code": return_code,
                },
            )

            logger.info("Run %d finished with code %d", run_id, return_code)

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error monitoring run %d", run_id)
            await ws_manager.broadcast(run_id, {"type": "run_error", "run_id": run_id})
        finally:
            log_file.close()
            self._cleanup_run(run_id)

    async def _record_metric(
        self,
        run_id: int,
        metric_data: dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Persist a metric and broadcast via WebSocket."""
        step = metric_data["step"]
        epoch = metric_data.get("epoch")
        metrics_json = {k: v for k, v in metric_data.items() if k not in ("step", "epoch")}

        if not metrics_json:
            return

        log_entry = MetricLog(
            run_id=run_id,
            step=step,
            epoch=epoch,
            metrics_json=metrics_json,
            timestamp=datetime.utcnow(),
        )
        session.add(log_entry)
        await session.commit()

        await ws_manager.broadcast(
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

    async def _collect_final_metrics(
        self,
        run: ExperimentRun,
        session: AsyncSession,
    ) -> None:
        """Aggregate final metrics from MetricLog entries into metrics_summary.

        Collects the last recorded value for each metric key and adds
        training duration. Called automatically when a run finishes.
        """
        run_id = run.id
        result = await session.execute(
            select(MetricLog).where(MetricLog.run_id == run_id).order_by(MetricLog.step)
        )
        logs = result.scalars().all()

        if not logs:
            # No metrics recorded — still store duration
            duration = None
            if run.started_at and run.ended_at:
                duration = (run.ended_at - run.started_at).total_seconds()
            run.metrics_summary = {"_duration_seconds": duration, "_total_steps": 0}
            return

        # Build last-value map: for each metric key, keep the last value seen
        last_values: dict[str, Any] = {}
        max_step = 0
        max_epoch: int | None = None
        for log in logs:
            for k, v in (log.metrics_json or {}).items():
                last_values[k] = v
            if log.step > max_step:
                max_step = log.step
            if log.epoch is not None:
                max_epoch = log.epoch

        # Calculate duration
        duration = None
        if run.started_at and run.ended_at:
            duration = (run.ended_at - run.started_at).total_seconds()

        # Build summary
        summary: dict[str, Any] = {**last_values}
        summary["_duration_seconds"] = duration
        summary["_total_steps"] = max_step
        if max_epoch is not None:
            summary["_total_epochs"] = max_epoch
        summary["_num_metric_logs"] = len(logs)

        run.metrics_summary = summary
        logger.info(
            "Collected metrics_summary for run %d: %d keys, %d steps",
            run_id,
            len(last_values),
            max_step,
        )

    async def _send_run_notification(
        self,
        run: ExperimentRun,
        session: AsyncSession,
    ) -> None:
        """Send notification for a completed/failed run."""
        from backend.services.notifier import notify_run_completed, notify_run_failed

        # Get experiment name
        result = await session.execute(
            select(ExperimentConfig).where(ExperimentConfig.id == run.experiment_config_id)
        )
        experiment = result.scalar_one_or_none()
        exp_name = experiment.name if experiment else f"Experiment #{run.experiment_config_id}"

        duration = None
        if run.started_at and run.ended_at:
            duration = (run.ended_at - run.started_at).total_seconds()

        try:
            if run.status == RunStatus.COMPLETED:
                await notify_run_completed(
                    experiment_name=exp_name,
                    run_id=run.id,  # type: ignore[arg-type]
                    metrics_summary=run.metrics_summary,
                    duration_seconds=duration,
                )
            elif run.status == RunStatus.FAILED:
                # Read last 10 log lines
                last_log = None
                if run.log_path:
                    try:
                        from pathlib import Path

                        log_file = Path(run.log_path)
                        if log_file.exists():
                            lines = log_file.read_text().strip().split("\n")
                            last_log = "\n".join(lines[-10:])
                    except Exception:
                        pass

                await notify_run_failed(
                    experiment_name=exp_name,
                    run_id=run.id,  # type: ignore[arg-type]
                    duration_seconds=duration,
                    last_log_lines=last_log,
                )
        except Exception:
            logger.warning("Failed to send notification for run %d", run.id)

    def _cleanup_run(self, run_id: int) -> None:
        """Remove all in-memory tracking state for a run."""
        self._processes.pop(run_id, None)
        self._monitors.pop(run_id, None)
        self._adapters.pop(run_id, None)

        # Remove temp config file
        config_path = self._config_files.pop(run_id, None)
        if config_path and os.path.exists(config_path):
            try:
                os.unlink(config_path)
            except OSError:
                pass


# Global runner instance
runner = ExperimentRunner()
