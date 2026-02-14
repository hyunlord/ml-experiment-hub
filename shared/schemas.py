"""Shared Pydantic schemas and enums for ML Experiment Hub."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExperimentConfigStatus(str, Enum):
    """Status of an experiment configuration."""

    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(str, Enum):
    """Status of an experiment run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Type of background job."""

    EVAL = "eval"
    INDEX_BUILD = "index_build"


class JobStatus(str, Enum):
    """Status of a background job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetricPoint(BaseModel):
    """A single metric log entry with free-form key-value metrics."""

    step: int = Field(ge=0, description="Training step number")
    epoch: int | None = Field(default=None, ge=0, description="Epoch number")
    timestamp: datetime = Field(description="When the metrics were recorded")
    metrics_json: dict[str, Any] = Field(
        description="Free-form metrics (e.g. {'train/loss': 0.5, 'val/map': 0.8})"
    )


class SystemStatsPoint(BaseModel):
    """System resource utilization snapshot."""

    timestamp: datetime
    gpu_util: float | None = None
    gpu_memory_used: float | None = None
    gpu_memory_total: float | None = None
    cpu_percent: float | None = None
    ram_percent: float | None = None
