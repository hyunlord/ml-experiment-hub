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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown."""
    # Startup: Initialize database
    await init_db()

    # Clean up stale runs from previous server session
    from datetime import datetime

    from sqlmodel import select

    from backend.models.database import async_session_maker
    from backend.models.experiment import ExperimentRun, Job, OptunaStudy
    from shared.schemas import JobStatus, RunStatus

    async with async_session_maker() as session:
        result = await session.execute(
            select(ExperimentRun).where(ExperimentRun.status == RunStatus.RUNNING)
        )
        stale_runs = result.scalars().all()
        if stale_runs:
            for run in stale_runs:
                run.status = RunStatus.FAILED
                run.ended_at = datetime.utcnow()
            await session.commit()
            import logging

            logging.getLogger(__name__).warning(
                "Cleaned up %d stale RUNNING runs from previous server session",
                len(stale_runs),
            )

        # Clean up stale jobs
        result = await session.execute(select(Job).where(Job.status == JobStatus.RUNNING))
        stale_jobs = result.scalars().all()
        if stale_jobs:
            for job in stale_jobs:
                job.status = JobStatus.FAILED
                job.ended_at = datetime.utcnow()
                job.error_message = "Server restarted"
            await session.commit()
            import logging

            logging.getLogger(__name__).warning(
                "Cleaned up %d stale RUNNING jobs from previous server session",
                len(stale_jobs),
            )

        # Clean up stale optuna studies
        result = await session.execute(
            select(OptunaStudy).where(OptunaStudy.status == JobStatus.RUNNING)
        )
        stale_studies = result.scalars().all()
        if stale_studies:
            for study in stale_studies:
                study.status = JobStatus.FAILED
            await session.commit()

        # Clean up stale queue entries
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

        # Clean up stale prepare jobs on datasets
        result = await session.execute(
            select(DatasetDefinition).where(DatasetDefinition.prepare_job_id.is_not(None))  # type: ignore[union-attr]
        )
        stale_ds = result.scalars().all()
        if stale_ds:
            for ds in stale_ds:
                ds.prepare_job_id = None
            await session.commit()

        # Seed dataset definitions
        from backend.services.dataset_registry import seed_datasets

        await seed_datasets(session)

    # Start system monitor service
    from backend.core.system_monitor import system_monitor

    system_monitor.start()

    # Start queue scheduler
    from backend.services.queue_scheduler import queue_scheduler

    queue_scheduler.start()

    yield

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
