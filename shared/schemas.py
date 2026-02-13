"""Shared Pydantic schemas for ML Experiment Hub."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExperimentStatus(str, Enum):
    """Status of an experiment."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MetricPoint(BaseModel):
    """A single metric measurement at a specific point in time."""

    timestamp: datetime = Field(description="When the metric was recorded")
    step: int = Field(ge=0, description="Training step number")
    name: str = Field(min_length=1, description="Name of the metric (e.g., 'loss', 'accuracy')")
    value: float = Field(description="Value of the metric")


class ExperimentConfig(BaseModel):
    """Configuration for launching an ML experiment."""

    name: str = Field(min_length=1, description="Human-readable experiment name")
    description: str = Field(default="", description="Optional experiment description")
    framework: str = Field(
        min_length=1,
        description="ML framework (e.g., 'pytorch_lightning', 'huggingface')",
    )
    script_path: str = Field(min_length=1, description="Path to the training script")
    hyperparameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Hyperparameters for the experiment",
    )
    tags: list[str] = Field(default_factory=list, description="Tags for categorizing experiments")


class ExperimentResult(BaseModel):
    """Result data from a completed or running experiment."""

    experiment_id: str = Field(min_length=1, description="Unique identifier for the experiment")
    status: ExperimentStatus = Field(description="Current status of the experiment")
    metrics: list[MetricPoint] = Field(
        default_factory=list,
        description="List of metric measurements",
    )
    start_time: datetime = Field(description="When the experiment started")
    end_time: datetime | None = Field(default=None, description="When the experiment ended")
