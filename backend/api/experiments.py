"""REST API endpoints for experiment management."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.models.database import get_session
from backend.models.experiment import ExperimentRun, MetricLog
from backend.schemas.experiment import (
    CompareExperimentEntry,
    CompareRequest,
    CompareResponse,
    DryRunResponse,
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
        skip=skip,
        limit=limit,
        status=status,
        schema_id=schema_id,
        tags=tags,
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


@router.post("/{experiment_id}/dry-run", response_model=DryRunResponse)
async def dry_run_experiment(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DryRunResponse:
    """Generate config YAML and command without launching training."""
    import os
    from pathlib import Path

    from adapters.pytorch_lightning import PyTorchLightningAdapter
    from shared.utils import unflatten_dict

    service = ExperimentService(session)
    experiment = await service.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Get adapter and convert flat config to nested
    adapter = PyTorchLightningAdapter()
    flat_config = experiment.config_json
    nested_config = unflatten_dict(flat_config)

    # Generate YAML and command
    config_yaml = adapter.config_to_yaml(nested_config)
    command = adapter.get_train_command("/tmp/placeholder.yaml")

    # Working directory
    projects_dir = os.environ.get("PROJECTS_DIR", "./projects")
    working_dir = str(Path(projects_dir).resolve())

    # Validate and generate warnings
    warnings = []
    data_dir = os.environ.get("DATA_DIR", "./data")

    # Check data.data_root
    if "data" in nested_config and isinstance(nested_config["data"], dict):
        data_root = nested_config["data"].get("data_root")
        if data_root:
            data_root_path = Path(data_dir) / data_root
            if not data_root_path.exists():
                warnings.append(f"data.data_root path not found: {data_root_path}")

        # Check extra_datasets paths
        extra_datasets = nested_config["data"].get("extra_datasets")
        if isinstance(extra_datasets, list):
            for ds in extra_datasets:
                if isinstance(ds, dict):
                    jsonl_path = ds.get("jsonl_path")
                    if jsonl_path and not Path(jsonl_path).exists():
                        warnings.append(f"Dataset jsonl_path not found: {jsonl_path}")

    # Check batch_size auto
    if "training" in nested_config and isinstance(nested_config["training"], dict):
        batch_size = nested_config["training"].get("batch_size")
        if batch_size == "auto":
            warnings.append(
                "training.batch_size set to 'auto' - will be resolved at runtime based on GPU memory"
            )

    return DryRunResponse(
        config_yaml=config_yaml,
        command=command,
        working_dir=working_dir,
        effective_config=nested_config,
        warnings=warnings,
    )


@router.post("/compare", response_model=CompareResponse)
async def compare_experiments(
    body: CompareRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CompareResponse:
    """Compare multiple experiments: configs + latest run metrics."""
    service = ExperimentService(session)
    entries: list[CompareExperimentEntry] = []

    for exp_id in body.ids:
        experiment = await service.get_experiment(exp_id)
        if not experiment:
            raise HTTPException(status_code=404, detail=f"Experiment {exp_id} not found")

        # Get latest run's metrics_summary
        result = await session.execute(
            select(ExperimentRun)
            .where(ExperimentRun.experiment_config_id == exp_id)
            .order_by(ExperimentRun.started_at.desc())
            .limit(1)
        )
        latest_run = result.scalar_one_or_none()

        entries.append(
            CompareExperimentEntry(
                id=experiment.id,  # type: ignore[arg-type]
                name=experiment.name,
                config=experiment.config_json or {},
                metrics_summary=latest_run.metrics_summary if latest_run else None,
                status=experiment.status.value,
            )
        )

    # Find config keys that differ across experiments
    all_keys: set[str] = set()
    configs = [e.config for e in entries]
    for cfg in configs:
        all_keys.update(cfg.keys())

    diff_keys: list[str] = []
    for key in sorted(all_keys):
        values = [cfg.get(key) for cfg in configs]
        if len(set(str(v) for v in values)) > 1:
            diff_keys.append(key)

    return CompareResponse(experiments=entries, config_diff_keys=diff_keys)


@router.get("/{experiment_id}/metrics")
async def get_experiment_metrics(
    experiment_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    """Get metrics from the latest run of an experiment.

    Convenience endpoint: finds the latest run and returns its metric logs
    as a flat list of {step, name, value} for the compare page.
    """
    # Find the latest run
    result = await session.execute(
        select(ExperimentRun)
        .where(ExperimentRun.experiment_config_id == experiment_id)
        .order_by(ExperimentRun.started_at.desc())
        .limit(1)
    )
    latest_run = result.scalar_one_or_none()
    if not latest_run:
        return []

    # Fetch metric logs for that run
    result = await session.execute(
        select(MetricLog).where(MetricLog.run_id == latest_run.id).order_by(MetricLog.step)
    )
    logs = result.scalars().all()

    # Flatten to {step, name, value} format expected by compare page
    points: list[dict[str, Any]] = []
    for log in logs:
        for key, value in (log.metrics_json or {}).items():
            if isinstance(value, (int, float)):
                points.append({"step": log.step, "name": key, "value": value})

    return points
