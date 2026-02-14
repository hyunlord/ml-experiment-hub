"""REST API endpoints for experiment run management."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.core.process_manager import runner
from backend.models.database import get_session
from backend.models.experiment import ExperimentRun, MetricLog
from backend.schemas.experiment import (
    CheckpointEntry,
    CheckpointsResponse,
    MetricLogResponse,
    RunResponse,
    RunSummaryResponse,
)

router = APIRouter(prefix="/api", tags=["runs"])


@router.post("/experiments/{experiment_id}/runs", response_model=RunResponse, status_code=201)
async def start_run(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RunResponse:
    """Start a new run for an experiment.

    Args:
        experiment_id: ID of the ExperimentConfig to run.
        session: Database session.

    Returns:
        The created ExperimentRun.

    Raises:
        HTTPException: If experiment not found or not in runnable state.
    """
    try:
        run = await runner.start(experiment_id, session)
        return RunResponse.model_validate(run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/runs/{run_id}/stop")
async def stop_run(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Stop a running run.

    Args:
        run_id: ID of the ExperimentRun to stop.
        session: Database session.

    Returns:
        Status confirmation.

    Raises:
        HTTPException: If run not found or not running.
    """
    stopped = await runner.stop(run_id, session)
    if not stopped:
        raise HTTPException(status_code=404, detail="Run not found or not running")
    return {"status": "ok"}


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RunResponse:
    """Get run details.

    Args:
        run_id: ID of the ExperimentRun.
        session: Database session.

    Returns:
        Run details.

    Raises:
        HTTPException: If run not found.
    """
    result = await session.execute(select(ExperimentRun).where(ExperimentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse.model_validate(run)


@router.get("/experiments/{experiment_id}/runs", response_model=list[RunResponse])
async def list_runs(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[RunResponse]:
    """List runs for an experiment.

    Args:
        experiment_id: ID of the ExperimentConfig.
        session: Database session.

    Returns:
        List of runs for the experiment.
    """
    result = await session.execute(
        select(ExperimentRun)
        .where(ExperimentRun.experiment_config_id == experiment_id)
        .order_by(ExperimentRun.started_at.desc())
    )
    runs = result.scalars().all()
    return [RunResponse.model_validate(run) for run in runs]


@router.get("/runs/{run_id}/metrics", response_model=list[MetricLogResponse])
async def get_run_metrics(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    step_from: int | None = Query(default=None, ge=0),
    step_to: int | None = Query(default=None, ge=0),
) -> list[MetricLogResponse]:
    """Get metrics for a run.

    Args:
        run_id: ID of the ExperimentRun.
        session: Database session.
        step_from: Optional minimum step (inclusive).
        step_to: Optional maximum step (inclusive).

    Returns:
        List of metric logs for the run.
    """
    query = select(MetricLog).where(MetricLog.run_id == run_id)

    if step_from is not None:
        query = query.where(MetricLog.step >= step_from)
    if step_to is not None:
        query = query.where(MetricLog.step <= step_to)

    query = query.order_by(MetricLog.step)

    result = await session.execute(query)
    metrics = result.scalars().all()
    return [MetricLogResponse.model_validate(metric) for metric in metrics]


@router.get("/runs/{run_id}/summary", response_model=RunSummaryResponse)
async def get_run_summary(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RunSummaryResponse:
    """Get result summary for a completed run.

    Returns metrics_summary, training duration, and status.
    """
    result = await session.execute(select(ExperimentRun).where(ExperimentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    duration: float | None = None
    if run.started_at and run.ended_at:
        duration = (run.ended_at - run.started_at).total_seconds()

    return RunSummaryResponse(
        run_id=run.id,  # type: ignore[arg-type]
        experiment_config_id=run.experiment_config_id,
        status=run.status,
        metrics_summary=run.metrics_summary or {},
        started_at=run.started_at,
        ended_at=run.ended_at,
        duration_seconds=duration,
    )


@router.get("/runs/{run_id}/checkpoints", response_model=CheckpointsResponse)
async def get_run_checkpoints(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CheckpointsResponse:
    """Get checkpoint files for a run.

    Scans the checkpoint_path directory for checkpoint files and returns
    their paths, sizes, and modification times.
    """
    result = await session.execute(select(ExperimentRun).where(ExperimentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    checkpoints: list[CheckpointEntry] = []
    total_size = 0

    if run.checkpoint_path:
        ckpt_path = Path(run.checkpoint_path)
        if ckpt_path.is_dir():
            # Scan directory for checkpoint files
            for f in sorted(ckpt_path.iterdir()):
                if f.is_file() and f.suffix in (".pt", ".pth", ".ckpt", ".bin", ".safetensors"):
                    stat = f.stat()
                    checkpoints.append(
                        CheckpointEntry(
                            path=str(f),
                            size_bytes=stat.st_size,
                            modified_at=datetime.fromtimestamp(stat.st_mtime),
                        )
                    )
                    total_size += stat.st_size
        elif ckpt_path.is_file():
            stat = ckpt_path.stat()
            checkpoints.append(
                CheckpointEntry(
                    path=str(ckpt_path),
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                )
            )
            total_size = stat.st_size

    return CheckpointsResponse(
        run_id=run.id,  # type: ignore[arg-type]
        checkpoint_path=run.checkpoint_path,
        checkpoints=checkpoints,
        total_size_bytes=total_size,
    )
