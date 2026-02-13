"""Experiment database models."""

from datetime import datetime
from typing import Any

from sqlmodel import Column, Field, JSON, SQLModel

from shared.schemas import ExperimentStatus


class Experiment(SQLModel, table=True):
    """Experiment database model."""

    __tablename__ = "experiments"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    status: ExperimentStatus = Field(default=ExperimentStatus.PENDING)
    framework: str
    script_path: str
    hyperparameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class MetricRecord(SQLModel, table=True):
    """Metric record database model."""

    __tablename__ = "metric_records"

    id: int | None = Field(default=None, primary_key=True)
    experiment_id: int = Field(foreign_key="experiments.id", index=True)
    step: int = Field(ge=0)
    name: str
    value: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
