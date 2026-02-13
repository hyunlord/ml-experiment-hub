"""Core database models for ML Experiment Hub."""

from datetime import datetime
from typing import Any

from sqlmodel import Column, Field, JSON, Relationship, SQLModel

from shared.schemas import ExperimentConfigStatus, RunStatus


class ConfigSchema(SQLModel, table=True):
    """Reusable configuration schema template.

    Defines the expected fields and their types for experiment configs.
    Users can create templates like "image classification" or "cross-modal-hash"
    and the frontend auto-generates forms from fields_schema.

    Example fields_schema:
        {
            "backbone": {"type": "select", "options": ["resnet50", "siglip2", "vit_b"]},
            "batch_size": {"type": "number", "min": 1, "max": 2048},
            "learning_rate": {"type": "number", "min": 0.0, "max": 1.0, "step": 0.0001},
            "optimizer": {"type": "select", "options": ["adam", "sgd", "adamw"]}
        }
    """

    __tablename__ = "config_schemas"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    fields_schema: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    experiment_configs: list["ExperimentConfig"] = Relationship(back_populates="config_schema")


class ExperimentConfig(SQLModel, table=True):
    """Experiment configuration — the central entity.

    config_json is a completely free-form key-value store.
    Users can add any fields they need (backbone, batch_size, learning_rate, etc.)
    without being constrained to a fixed schema. Optionally link to a ConfigSchema
    for form generation and validation.
    """

    __tablename__ = "experiment_configs"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    config_schema_id: int | None = Field(default=None, foreign_key="config_schemas.id")
    status: ExperimentConfigStatus = Field(default=ExperimentConfigStatus.DRAFT)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    config_schema: ConfigSchema | None = Relationship(back_populates="experiment_configs")
    runs: list["ExperimentRun"] = Relationship(back_populates="experiment_config")


class ExperimentRun(SQLModel, table=True):
    """A single execution of an experiment configuration.

    One ExperimentConfig can have multiple runs (retries, different seeds, etc.).
    Tracks process ID, log paths, and final metric summaries.
    """

    __tablename__ = "experiment_runs"

    id: int | None = Field(default=None, primary_key=True)
    experiment_config_id: int = Field(foreign_key="experiment_configs.id", index=True)
    status: RunStatus = Field(default=RunStatus.RUNNING)
    pid: int | None = Field(default=None, description="System process ID")
    log_path: str | None = Field(default=None, description="Path to log file")
    metrics_summary: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Final aggregated metrics",
    )
    checkpoint_path: str | None = Field(default=None, description="Best checkpoint path")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = Field(default=None)

    # Relationships
    experiment_config: ExperimentConfig = Relationship(back_populates="runs")
    metric_logs: list["MetricLog"] = Relationship(back_populates="run")
    system_stats: list["SystemStats"] = Relationship(back_populates="run")


class MetricLog(SQLModel, table=True):
    """Real-time metric log entry.

    metrics_json is free-form to accommodate any model's metrics.
    Examples: {"train/loss": 0.5, "val/map": 0.8, "lr": 0.001}
    """

    __tablename__ = "metric_logs"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="experiment_runs.id", index=True)
    step: int = Field(ge=0)
    epoch: int | None = Field(default=None, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metrics_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Relationships
    run: ExperimentRun = Relationship(back_populates="metric_logs")


class SystemStats(SQLModel, table=True):
    """GPU/CPU/Memory monitoring snapshot per run."""

    __tablename__ = "system_stats"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="experiment_runs.id", index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    gpu_util: float | None = Field(default=None, description="GPU utilization %")
    gpu_memory_used: float | None = Field(default=None, description="GPU memory used (MB)")
    gpu_memory_total: float | None = Field(default=None, description="GPU memory total (MB)")
    cpu_percent: float | None = Field(default=None, description="CPU utilization %")
    ram_percent: float | None = Field(default=None, description="RAM utilization %")

    # Relationships
    run: ExperimentRun = Relationship(back_populates="system_stats")
