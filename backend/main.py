"""FastAPI application entry point for ML Experiment Hub."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import (
    compat,
    datasets,
    experiments,
    jobs,
    metrics,
    queue,
    runs,
    schemas,
    search,
    settings as settings_api,
    studies,
    system,
)
from backend.config import settings
from backend.models.database import init_db


def _is_pid_alive(pid: int | None) -> bool:
    """Check if a process with the given PID is still running."""
    if pid is None:
        return False
    try:
        import os

        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown."""
    import logging
    from datetime import datetime

    from sqlmodel import select

    from backend.models.database import async_session_maker
    from backend.models.experiment import ExperimentRun, Job, OptunaStudy
    from shared.schemas import JobStatus, RunStatus

    _logger = logging.getLogger(__name__)

    # Startup: Initialize database (with WAL mode for SQLite)
    await init_db()

    # Enable WAL mode for SQLite
    from backend.models.database import engine

    if "sqlite" in str(engine.url):
        async with engine.begin() as conn:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
            _logger.info("SQLite WAL mode enabled")

    async with async_session_maker() as session:
        # ── Recover or fail stale RUNNING runs ──
        result = await session.execute(
            select(ExperimentRun).where(ExperimentRun.status == RunStatus.RUNNING)
        )
        stale_runs = result.scalars().all()
        recovered_count = 0
        failed_count = 0
        for run in stale_runs:
            if _is_pid_alive(run.pid):
                # Process still alive — log but leave as RUNNING
                _logger.info(
                    "Run %d (PID %d) still alive after restart, keeping RUNNING",
                    run.id,
                    run.pid,
                )
                recovered_count += 1
            else:
                run.status = RunStatus.FAILED
                run.ended_at = datetime.utcnow()
                failed_count += 1
        if stale_runs:
            await session.commit()
            _logger.warning(
                "Startup recovery: %d runs still alive, %d marked FAILED",
                recovered_count,
                failed_count,
            )

        # ── Recover or fail stale RUNNING jobs ──
        result = await session.execute(select(Job).where(Job.status == JobStatus.RUNNING))
        stale_jobs = result.scalars().all()
        for job in stale_jobs:
            if _is_pid_alive(job.pid):
                _logger.info(
                    "Job %d (PID %d) still alive after restart, keeping RUNNING",
                    job.id,
                    job.pid,
                )
            else:
                job.status = JobStatus.FAILED
                job.ended_at = datetime.utcnow()
                job.error_message = "Server restarted — process not found"
        if stale_jobs:
            await session.commit()

        # ── Fail stale optuna studies ──
        result = await session.execute(
            select(OptunaStudy).where(OptunaStudy.status == JobStatus.RUNNING)
        )
        stale_studies = result.scalars().all()
        if stale_studies:
            for study in stale_studies:
                study.status = JobStatus.FAILED
            await session.commit()

        # ── Fail stale queue entries ──
        from backend.models.experiment import DatasetDefinition, QueueEntry
        from shared.schemas import QueueStatus

        result = await session.execute(
            select(QueueEntry).where(QueueEntry.status == QueueStatus.RUNNING)
        )
        stale_queue = result.scalars().all()
        if stale_queue:
            for qe in stale_queue:
                qe.status = QueueStatus.FAILED
                qe.error_message = "Server restarted"
            await session.commit()

        # ── Clean up stale prepare jobs on datasets ──
        result = await session.execute(
            select(DatasetDefinition).where(DatasetDefinition.prepare_job_id.is_not(None))  # type: ignore[union-attr]
        )
        stale_ds = result.scalars().all()
        if stale_ds:
            for ds in stale_ds:
                ds.prepare_job_id = None
            await session.commit()

        # ── Seed dataset definitions ──
        from backend.services.dataset_registry import seed_datasets

        await seed_datasets(session)

    # Start system monitor service
    from backend.core.system_monitor import system_monitor

    system_monitor.start()

    # Start queue scheduler
    from backend.services.queue_scheduler import queue_scheduler

    queue_scheduler.start()

    # Start log archive service
    from backend.services.log_manager import log_archive_service

    log_archive_service.start()

    yield

    # Shutdown: Stop log archive service
    from backend.services.log_manager import log_archive_service

    log_archive_service.stop()

    # Shutdown: Stop queue scheduler
    from backend.services.queue_scheduler import queue_scheduler

    queue_scheduler.stop()

    # Shutdown: Stop system monitor
    from backend.core.system_monitor import system_monitor

    system_monitor.stop()


# Create FastAPI application
app = FastAPI(
    title="ML Experiment Hub API",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(experiments.router)
app.include_router(schemas.router)
app.include_router(metrics.router)
app.include_router(runs.router)
app.include_router(compat.router)
app.include_router(datasets.router)
app.include_router(system.router)
app.include_router(jobs.router)
app.include_router(search.router)
app.include_router(studies.router)
app.include_router(queue.router)
app.include_router(settings_api.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "ML Experiment Hub API", "version": "0.1.0"}
