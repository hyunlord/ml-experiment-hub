"""FastAPI application entry point for ML Experiment Hub."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import compat, datasets, experiments, metrics, runs, schemas, system
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
    from backend.models.experiment import ExperimentRun
    from shared.schemas import RunStatus

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

    # Start system monitor service
    from backend.core.system_monitor import system_monitor
    system_monitor.start()

    yield

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


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "ML Experiment Hub API", "version": "0.1.0"}
