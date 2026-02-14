"""REST API endpoints for Optuna hyperparameter search studies."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from backend.models.database import get_session
from backend.models.experiment import (
    ExperimentConfig,
    OptunaStudy,
    OptunaTrialResult,
)
from backend.schemas.optuna import (
    CreateExperimentFromTrialRequest,
    CreateStudyRequest,
    ParamImportanceResponse,
    StudyResponse,
    StudySummaryResponse,
    TrialProgressUpdate,
    TrialResultResponse,
)
from backend.services.job_manager import job_manager
from shared.schemas import ExperimentConfigStatus, JobStatus, JobType

router = APIRouter(prefix="/api/studies", tags=["studies"])


@router.post("", response_model=StudyResponse, status_code=201)
async def create_study(
    body: CreateStudyRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StudyResponse:
    """Create a new Optuna study."""
    study = OptunaStudy(
        name=body.name,
        config_schema_id=body.config_schema_id,
        base_config_json=body.base_config_json,
        search_space_json=body.search_space_json,
        n_trials=body.n_trials,
        search_epochs=body.search_epochs,
        subset_ratio=body.subset_ratio,
        pruner=body.pruner,
        objective_metric=body.objective_metric,
        direction=body.direction,
    )
    session.add(study)
    await session.commit()
    await session.refresh(study)
    return StudyResponse.model_validate(study)


@router.post("/{study_id}/start", response_model=StudyResponse)
async def start_study(
    study_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StudyResponse:
    """Start an Optuna search study as a background job."""
    result = await session.execute(
        select(OptunaStudy)
        .options(selectinload(OptunaStudy.trials))
        .where(OptunaStudy.id == study_id)
    )
    study = result.scalar_one_or_none()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    if study.status == JobStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Study already running")

    # Create a Job for the study — use run_id=0 as sentinel (no specific run)
    config: dict[str, Any] = {
        "study_id": study.id,
        "search_space": study.search_space_json,
        "base_config": study.base_config_json,
        "n_trials": study.n_trials,
        "search_epochs": study.search_epochs,
        "subset_ratio": study.subset_ratio,
        "pruner": study.pruner,
        "objective_metric": study.objective_metric,
        "direction": study.direction,
    }

    from backend.models.experiment import Job

    job = Job(
        job_type=JobType.OPTUNA_SEARCH,
        run_id=0,
        status=JobStatus.PENDING,
        config_json=config,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    study.status = JobStatus.RUNNING
    study.job_id = job.id
    await session.commit()

    # Launch the job subprocess
    await job_manager._launch_job(job, "optuna_search", session)

    await session.refresh(study)
    return StudyResponse.model_validate(study)


@router.get("", response_model=list[StudySummaryResponse])
async def list_studies(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[StudySummaryResponse]:
    """List all studies."""
    result = await session.execute(select(OptunaStudy).order_by(OptunaStudy.created_at.desc()))
    studies = result.scalars().all()
    return [StudySummaryResponse.model_validate(s) for s in studies]


@router.get("/{study_id}", response_model=StudyResponse)
async def get_study(
    study_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StudyResponse:
    """Get study details with all trials."""
    result = await session.execute(
        select(OptunaStudy)
        .options(selectinload(OptunaStudy.trials))
        .where(OptunaStudy.id == study_id)
    )
    study = result.scalar_one_or_none()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    return StudyResponse.model_validate(study)


@router.get("/{study_id}/trials", response_model=list[TrialResultResponse])
async def list_trials(
    study_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TrialResultResponse]:
    """List trials for a study."""
    result = await session.execute(
        select(OptunaTrialResult)
        .where(OptunaTrialResult.study_id == study_id)
        .order_by(OptunaTrialResult.trial_number)
    )
    trials = result.scalars().all()
    return [TrialResultResponse.model_validate(t) for t in trials]


@router.post("/{study_id}/trial-progress", response_model=TrialResultResponse)
async def update_trial_progress(
    study_id: int,
    body: TrialProgressUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TrialResultResponse:
    """Internal endpoint: update trial progress from subprocess."""
    # Find or create trial result
    result = await session.execute(
        select(OptunaTrialResult).where(
            OptunaTrialResult.study_id == study_id,
            OptunaTrialResult.trial_number == body.trial_number,
        )
    )
    trial = result.scalar_one_or_none()

    if trial is None:
        trial = OptunaTrialResult(
            study_id=study_id,
            trial_number=body.trial_number,
            params_json=body.params_json,
            status=body.status,
        )
        session.add(trial)
    else:
        trial.status = body.status
        if body.params_json:
            trial.params_json = body.params_json

    if body.objective_value is not None:
        trial.objective_value = body.objective_value
    if body.duration_seconds is not None:
        trial.duration_seconds = body.duration_seconds
    if body.intermediate_values_json:
        trial.intermediate_values_json = body.intermediate_values_json

    await session.commit()
    await session.refresh(trial)

    # Update study best if completed
    if body.status.value == "completed" and body.objective_value is not None:
        study_result = await session.execute(select(OptunaStudy).where(OptunaStudy.id == study_id))
        study = study_result.scalar_one_or_none()
        if study:
            is_better = study.best_value is None or (
                (study.direction == "maximize" and body.objective_value > study.best_value)
                or (study.direction == "minimize" and body.objective_value < study.best_value)
            )
            if is_better:
                study.best_trial_number = body.trial_number
                study.best_value = body.objective_value
                await session.commit()

    return TrialResultResponse.model_validate(trial)


@router.post("/{study_id}/complete")
async def mark_study_complete(
    study_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Internal endpoint: mark study as completed."""
    from datetime import datetime

    result = await session.execute(select(OptunaStudy).where(OptunaStudy.id == study_id))
    study = result.scalar_one_or_none()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    study.status = JobStatus.COMPLETED
    study.completed_at = datetime.utcnow()
    await session.commit()
    return {"status": "completed"}


@router.post("/{study_id}/cancel")
async def cancel_study(
    study_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Cancel a running study."""
    result = await session.execute(select(OptunaStudy).where(OptunaStudy.id == study_id))
    study = result.scalar_one_or_none()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    if study.job_id:
        await job_manager.cancel_job(study.job_id, session)

    study.status = JobStatus.CANCELLED
    await session.commit()
    return {"status": "cancelled"}


@router.post("/{study_id}/create-experiment", response_model=dict[str, Any])
async def create_experiment_from_trial(
    study_id: int,
    body: CreateExperimentFromTrialRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Create a new ExperimentConfig from the best (or specified) trial."""
    # Load study
    result = await session.execute(
        select(OptunaStudy)
        .options(selectinload(OptunaStudy.trials))
        .where(OptunaStudy.id == study_id)
    )
    study = result.scalar_one_or_none()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    # Find the trial
    if body.trial_id:
        trial_result = await session.execute(
            select(OptunaTrialResult).where(OptunaTrialResult.id == body.trial_id)
        )
        trial = trial_result.scalar_one_or_none()
    elif study.best_trial_number is not None:
        trial_result = await session.execute(
            select(OptunaTrialResult).where(
                OptunaTrialResult.study_id == study_id,
                OptunaTrialResult.trial_number == study.best_trial_number,
            )
        )
        trial = trial_result.scalar_one_or_none()
    else:
        raise HTTPException(status_code=400, detail="No best trial found")

    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")

    # Merge base config with trial params
    merged_config = {**study.base_config_json, **trial.params_json}

    exp_name = body.name or f"{study.name}-best-t{trial.trial_number}"
    experiment = ExperimentConfig(
        name=exp_name,
        description=f"Created from Optuna study '{study.name}', trial #{trial.trial_number} (objective={trial.objective_value})",
        config_json=merged_config,
        config_schema_id=study.config_schema_id,
        status=ExperimentConfigStatus.DRAFT,
        tags=body.tags or ["optuna-best"],
    )
    session.add(experiment)
    await session.commit()
    await session.refresh(experiment)

    return {"experiment_id": experiment.id, "name": experiment.name, "config": merged_config}


@router.get("/{study_id}/param-importance", response_model=ParamImportanceResponse)
async def get_param_importance(
    study_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ParamImportanceResponse:
    """Calculate parameter importance from completed trials."""
    result = await session.execute(
        select(OptunaTrialResult).where(
            OptunaTrialResult.study_id == study_id,
            OptunaTrialResult.status == "completed",
        )
    )
    trials = list(result.scalars().all())

    if len(trials) < 3:
        return ParamImportanceResponse(importances={})

    # Simple variance-based importance estimation
    param_keys = list(trials[0].params_json.keys())
    importances: dict[str, float] = {}
    objectives = [t.objective_value for t in trials if t.objective_value is not None]

    if not objectives:
        return ParamImportanceResponse(importances={})

    obj_variance = _variance(objectives)
    if obj_variance < 1e-10:
        return ParamImportanceResponse(importances={k: 1.0 / len(param_keys) for k in param_keys})

    for key in param_keys:
        values = [t.params_json.get(key) for t in trials]
        if all(isinstance(v, (int, float)) for v in values):
            corr = abs(
                _correlation(
                    [float(v) for v in values],  # type: ignore[arg-type]
                    [float(o) for o in objectives],
                )
            )
            importances[key] = corr
        else:
            importances[key] = 0.0

    # Normalize
    total = sum(importances.values()) or 1.0
    importances = {k: v / total for k, v in importances.items()}
    return ParamImportanceResponse(importances=importances)


def _variance(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / (n - 1)


def _correlation(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - 1)
    sx = _variance(xs) ** 0.5
    sy = _variance(ys) ** 0.5
    if sx < 1e-10 or sy < 1e-10:
        return 0.0
    return cov / (sx * sy)
