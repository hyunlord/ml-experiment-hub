"""REST API endpoints for experiment management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.models.database import get_session
from backend.models.experiment import MetricRecord
from backend.schemas.experiment import (
    ExperimentCreate,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentUpdate,
    MetricResponse,
)
from backend.services.experiment_service import ExperimentService
from shared.schemas import ExperimentStatus

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=ExperimentListResponse)
async def list_experiments(
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    status: ExperimentStatus | None = None,
) -> ExperimentListResponse:
    """List all experiments with pagination and optional status filter."""
    service = ExperimentService(session)
    experiments = await service.list_experiments(skip=skip, limit=limit, status=status)
    total = await service.count_experiments(status=status)
    return ExperimentListResponse(
        experiments=[ExperimentResponse.model_validate(exp) for exp in experiments],
        total=total,
    )


@router.post("", response_model=ExperimentResponse, status_code=201)
async def create_experiment(
    experiment: ExperimentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperimentResponse:
    """Create a new experiment."""
    service = ExperimentService(session)
    created = await service.create_experiment(experiment)
    return ExperimentResponse.model_validate(created)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperimentResponse:
    """Get experiment by ID."""
    service = ExperimentService(session)
    experiment = await service.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentResponse.model_validate(experiment)


@router.put("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: int,
    updates: ExperimentUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperimentResponse:
    """Update experiment details."""
    service = ExperimentService(session)
    experiment = await service.update_experiment(experiment_id, updates)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentResponse.model_validate(experiment)


@router.delete("/{experiment_id}", status_code=204)
async def delete_experiment(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete an experiment."""
    service = ExperimentService(session)
    deleted = await service.delete_experiment(experiment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Experiment not found")


@router.post("/{experiment_id}/start", response_model=ExperimentResponse)
async def start_experiment(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperimentResponse:
    """Start an experiment."""
    service = ExperimentService(session)
    experiment = await service.start_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentResponse.model_validate(experiment)


@router.post("/{experiment_id}/stop", response_model=ExperimentResponse)
async def stop_experiment(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperimentResponse:
    """Stop a running experiment."""
    service = ExperimentService(session)
    experiment = await service.stop_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentResponse.model_validate(experiment)


@router.get("/{experiment_id}/metrics", response_model=list[MetricResponse])
async def get_experiment_metrics(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MetricResponse]:
    """Get all metrics for an experiment."""
    # Verify experiment exists
    service = ExperimentService(session)
    experiment = await service.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Fetch metrics
    result = await session.execute(
        select(MetricRecord)
        .where(MetricRecord.experiment_id == experiment_id)
        .order_by(MetricRecord.timestamp)
    )
    metrics = result.scalars().all()
    return [MetricResponse.model_validate(metric) for metric in metrics]
