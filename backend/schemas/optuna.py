"""Optuna study schemas for API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas import JobStatus, TrialStatus


class SearchSpaceParam(BaseModel):
    """Definition of a single searchable parameter."""

    type: str = Field(description="float, int, or categorical")
    low: float | None = None
    high: float | None = None
    step: float | None = None
    log: bool = False
    choices: list[Any] | None = None


class CreateStudyRequest(BaseModel):
    """Request to create an Optuna study."""

    name: str
    config_schema_id: int | None = None
    base_config_json: dict[str, Any] = Field(default_factory=dict)
    search_space_json: dict[str, dict[str, Any]] = Field(
        description="Search space: {param_key: {type, low, high, ...}}"
    )
    n_trials: int = Field(default=20, ge=1, le=500)
    search_epochs: int = Field(default=5, ge=1, le=100)
    subset_ratio: float = Field(default=0.1, ge=0.01, le=1.0)
    pruner: str = Field(default="median")
    objective_metric: str = Field(default="val/map_i2t")
    direction: str = Field(default="maximize")


class TrialResultResponse(BaseModel):
    """Response for a single trial result."""

    id: int
    study_id: int
    trial_number: int
    params_json: dict[str, Any]
    objective_value: float | None
    status: TrialStatus
    duration_seconds: float | None
    intermediate_values_json: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class StudyResponse(BaseModel):
    """Response for a study."""

    id: int
    name: str
    config_schema_id: int | None
    base_config_json: dict[str, Any]
    search_space_json: dict[str, Any]
    n_trials: int
    search_epochs: int
    subset_ratio: float
    pruner: str
    objective_metric: str
    direction: str
    status: JobStatus
    best_trial_number: int | None
    best_value: float | None
    job_id: int | None
    created_at: datetime
    completed_at: datetime | None
    trials: list[TrialResultResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class StudySummaryResponse(BaseModel):
    """Lightweight study response without trials."""

    id: int
    name: str
    n_trials: int
    status: JobStatus
    best_trial_number: int | None
    best_value: float | None
    objective_metric: str
    direction: str
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class TrialProgressUpdate(BaseModel):
    """Progress update from the optuna runner subprocess."""

    study_id: int
    trial_number: int
    params_json: dict[str, Any] = Field(default_factory=dict)
    objective_value: float | None = None
    status: TrialStatus = TrialStatus.RUNNING
    duration_seconds: float | None = None
    intermediate_values_json: dict[str, Any] = Field(default_factory=dict)


class CreateExperimentFromTrialRequest(BaseModel):
    """Request to create an experiment from the best trial."""

    trial_id: int | None = None
    name: str | None = None
    tags: list[str] = Field(default_factory=list)


class ParamImportanceResponse(BaseModel):
    """Parameter importance scores."""

    importances: dict[str, float]
