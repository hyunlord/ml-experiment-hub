"""Experiment schemas for API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas import ExperimentConfigStatus, RunStatus


class ExperimentCreate(BaseModel):
    """Schema for creating an experiment configuration."""

    name: str = Field(min_length=1)
    description: str = Field(default="")
    config_json: dict[str, Any] = Field(default_factory=dict)
    config_schema_id: int | None = None
    tags: list[str] = Field(default_factory=list)


class ExperimentUpdate(BaseModel):
    """Schema for updating an experiment configuration."""

    name: str | None = None
    description: str | None = None
    config_json: dict[str, Any] | None = None
    tags: list[str] | None = None


class ExperimentResponse(BaseModel):
    """Schema for experiment configuration response."""

    id: int
    name: str
    description: str
    status: ExperimentConfigStatus
    config_json: dict[str, Any]
    config_schema_id: int | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class ExperimentListResponse(BaseModel):
    """Schema for experiment list response."""

    experiments: list[ExperimentResponse]
    total: int


class RunResponse(BaseModel):
    """Schema for experiment run response."""

    id: int
    experiment_config_id: int
    status: RunStatus
    pid: int | None
    log_path: str | None
    metrics_summary: dict[str, Any] | None
    checkpoint_path: str | None
    started_at: datetime | None
    ended_at: datetime | None

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class MetricLogResponse(BaseModel):
    """Schema for metric log response."""

    id: int
    run_id: int
    step: int
    epoch: int | None
    timestamp: datetime
    metrics_json: dict[str, Any]

    class Config:
        """Pydantic configuration."""

        from_attributes = True
