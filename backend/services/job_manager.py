"""Job management service for eval and index-build background tasks.

Jobs run as subprocesses with progress tracked via internal HTTP callbacks
to the hub (not stdout parsing).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.config import settings
from backend.models.experiment import ExperimentRun, Job
from shared.schemas import JobStatus, JobType

logger = logging.getLogger(__name__)


class JobManager:
    """Manages background jobs (eval, index build) as subprocesses."""

    def __init__(self) -> None:
        self._processes: dict[int, asyncio.subprocess.Process] = {}
        self._monitors: dict[int, asyncio.Task[None]] = {}

    async def create_eval_job(
        self,
        run_id: int,
        config: dict[str, Any],
        session: AsyncSession,
    ) -> Job:
        """Create and launch an evaluation job.

        Args:
            run_id: ID of the experiment run to evaluate.
            config: Job config (checkpoint, bit_lengths, k_values).
            session: Database session.

        Returns:
            The created Job record.
        """
        # Verify run exists
        result = await session.execute(select(ExperimentRun).where(ExperimentRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"Run {run_id} not found")

        job = Job(
            job_type=JobType.EVAL,
            run_id=run_id,
            status=JobStatus.PENDING,
            config_json=config,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        # Launch subprocess
        await self._launch_job(job, "eval", session)
        return job

    async def create_index_build_job(
        self,
        run_id: int,
        config: dict[str, Any],
        session: AsyncSession,
    ) -> Job:
        """Create and launch an index build job.

        Args:
            run_id: ID of the experiment run to build index from.
            config: Job config (checkpoint, image_dir, etc.).
            session: Database session.

        Returns:
            The created Job record.
        """
        result = await session.execute(select(ExperimentRun).where(ExperimentRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"Run {run_id} not found")

        job = Job(
            job_type=JobType.INDEX_BUILD,
            run_id=run_id,
            status=JobStatus.PENDING,
            config_json=config,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        await self._launch_job(job, "index_build", session)
        return job

    async def get_job(self, job_id: int, session: AsyncSession) -> Job | None:
        """Get a job by ID."""
        result = await session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        session: AsyncSession,
        job_type: JobType | None = None,
        run_id: int | None = None,
    ) -> list[Job]:
        """List jobs with optional filters."""
        query = select(Job)
        if job_type is not None:
            query = query.where(Job.job_type == job_type)
        if run_id is not None:
            query = query.where(Job.run_id == run_id)
        query = query.order_by(Job.created_at.desc())
        result = await session.execute(query)
        return list(result.scalars().all())

    async def update_progress(
        self,
        job_id: int,
        progress: int,
        session: AsyncSession,
        status: JobStatus | None = None,
        result_json: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> Job | None:
        """Update job progress from a running subprocess.

        This is called by the internal progress API endpoint.
        """
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return None

        job.progress = progress

        if status is not None:
            job.status = status
            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                job.ended_at = datetime.utcnow()

        if result_json is not None:
            job.result_json = result_json

        if error_message is not None:
            job.error_message = error_message

        await session.commit()
        await session.refresh(job)
        return job

    async def cancel_job(self, job_id: int, session: AsyncSession) -> bool:
        """Cancel a running job."""
        process = self._processes.get(job_id)
        if not process:
            return False

        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if job:
            job.status = JobStatus.CANCELLED
            job.ended_at = datetime.utcnow()
            await session.commit()

        self._cleanup(job_id)
        return True

    async def _launch_job(self, job: Job, job_type: str, session: AsyncSession) -> None:
        """Launch a job as a subprocess."""
        job_id = job.id
        assert job_id is not None

        # Write job config to temp file
        config_fd, config_path = tempfile.mkstemp(prefix=f"job_{job_id}_", suffix=".json")
        with os.fdopen(config_fd, "w") as f:
            json.dump(
                {
                    "job_id": job_id,
                    "job_type": job_type,
                    "run_id": job.run_id,
                    "config": job.config_json,
                    "server_url": "http://localhost:8002",
                },
                f,
            )

        # Build command
        cmd = [
            sys.executable,
            "-m",
            "backend.workers.job_runner",
            "--config",
            config_path,
        ]

        env = os.environ.copy()
        env["JOB_ID"] = str(job_id)
        env["JOB_CONFIG_PATH"] = config_path

        log_dir = Path(settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"job_{job_id}.log"
        log_file = open(log_path, "w")  # noqa: SIM115

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=log_file,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
        except Exception as e:
            log_file.close()
            os.unlink(config_path)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.ended_at = datetime.utcnow()
            await session.commit()
            raise ValueError(f"Failed to launch job: {e}") from e

        job.status = JobStatus.RUNNING
        job.pid = process.pid
        job.started_at = datetime.utcnow()
        await session.commit()

        self._processes[job_id] = process

        # Monitor completion
        monitor = asyncio.create_task(
            self._monitor(job_id, process, log_file, config_path, session)
        )
        self._monitors[job_id] = monitor

    async def _monitor(
        self,
        job_id: int,
        process: asyncio.subprocess.Process,
        log_file: Any,
        config_path: str,
        session: AsyncSession,
    ) -> None:
        """Monitor job subprocess for completion."""
        try:
            return_code = await process.wait()

            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job and job.status == JobStatus.RUNNING:
                if return_code == 0:
                    job.status = JobStatus.COMPLETED
                    job.progress = 100
                else:
                    job.status = JobStatus.FAILED
                    job.error_message = f"Process exited with code {return_code}"
                job.ended_at = datetime.utcnow()
                await session.commit()

            logger.info("Job %d finished with code %d", job_id, return_code)

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error monitoring job %d", job_id)
        finally:
            log_file.close()
            # Clean up config file
            try:
                os.unlink(config_path)
            except OSError:
                pass
            self._cleanup(job_id)

    def _cleanup(self, job_id: int) -> None:
        """Remove tracking state for a job."""
        self._processes.pop(job_id, None)
        self._monitors.pop(job_id, None)


# Global instance
job_manager = JobManager()
