"""Experiment schemas for API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas import ExperimentStatus


class ExperimentCreate(BaseModel):
    """Schema for creating an experiment."""

    name: str = Field(min_length=1)
    description: str = Field(default="")
    framework: str = Field(min_length=1)
    script_path: str = Field(min_length=1)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class ExperimentUpdate(BaseModel):
    """Schema for updating an experiment."""

    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class ExperimentResponse(BaseModel):
    """Schema for experiment response."""

    id: int
    name: str
    description: str
    status: ExperimentStatus
    framework: str
    script_path: str
    hyperparameters: dict[str, Any]
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class ExperimentListResponse(BaseModel):
    """Schema for experiment list response."""

    experiments: list[ExperimentResponse]
    total: int


class MetricResponse(BaseModel):
    """Schema for metric response."""

    id: int
    experiment_id: int
    step: int
    name: str
    value: float
    timestamp: datetime

    class Config:
        """Pydantic configuration."""

        from_attributes = True
