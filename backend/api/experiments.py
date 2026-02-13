"""REST API endpoints for experiment management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_session
from backend.schemas.experiment import (
    ExperimentCreate,
    ExperimentDiffRequest,
    ExperimentDiffResponse,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentUpdate,
)
from backend.services.experiment_service import ExperimentService
from shared.schemas import ExperimentConfigStatus

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("", response_model=ExperimentListResponse)
async def list_experiments(
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    status: ExperimentConfigStatus | None = None,
    schema_id: int | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
) -> ExperimentListResponse:
    """List experiment configurations with pagination and filters."""
    service = ExperimentService(session)
    experiments = await service.list_experiments(
        skip=skip, limit=limit, status=status, schema_id=schema_id, tags=tags,
    )
    total = await service.count_experiments(status=status, schema_id=schema_id)
    return ExperimentListResponse(
        experiments=[ExperimentResponse.from_model(exp) for exp in experiments],
        total=total,
    )


@router.post("", response_model=ExperimentResponse, status_code=201)
async def create_experiment(
    data: ExperimentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperimentResponse:
    """Create a new experiment configuration."""
    service = ExperimentService(session)
    created = await service.create_experiment(data)
    return ExperimentResponse.from_model(created)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperimentResponse:
    """Get experiment configuration by ID."""
    service = ExperimentService(session)
    experiment = await service.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentResponse.from_model(experiment)


@router.put("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: int,
    updates: ExperimentUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperimentResponse:
    """Update experiment configuration (draft status only)."""
    service = ExperimentService(session)
    experiment = await service.update_experiment(experiment_id, updates)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentResponse.from_model(experiment)


@router.delete("/{experiment_id}", status_code=204)
async def delete_experiment(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete an experiment configuration."""
    service = ExperimentService(session)
    deleted = await service.delete_experiment(experiment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Experiment not found")


@router.post("/{experiment_id}/clone", response_model=ExperimentResponse, status_code=201)
async def clone_experiment(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperimentResponse:
    """Clone an experiment (creates a new DRAFT with '(copy)' suffix)."""
    service = ExperimentService(session)
    clone = await service.clone_experiment(experiment_id)
    if not clone:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentResponse.from_model(clone)


@router.post("/{experiment_id}/diff", response_model=ExperimentDiffResponse)
async def diff_experiments(
    experiment_id: int,
    body: ExperimentDiffRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperimentDiffResponse:
    """Compare config of two experiments and return differences."""
    service = ExperimentService(session)
    diff = await service.diff_experiments(experiment_id, body.compare_with)
    return ExperimentDiffResponse(**diff)
