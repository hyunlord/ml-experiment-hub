"""Core database models for ML Experiment Hub."""

from datetime import datetime
from typing import Any

from sqlalchemy import Index
from sqlmodel import Column, Field, JSON, Relationship, SQLModel

from shared.schemas import (
    ExperimentConfigStatus,
    JobStatus,
    JobType,
    QueueStatus,
    RunStatus,
    TrialStatus,
)


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
    __table_args__ = (Index("ix_metric_logs_run_step", "run_id", "step"),)

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


class Job(SQLModel, table=True):
    """Background job for eval or index building.

    Jobs run as subprocesses with DB-based progress tracking.
    Results are stored in result_json on completion.
    """

    __tablename__ = "jobs"

    id: int | None = Field(default=None, primary_key=True)
    job_type: JobType = Field(description="Type of job (eval/index_build)")
    run_id: int = Field(foreign_key="experiment_runs.id", index=True)
    status: JobStatus = Field(default=JobStatus.PENDING)
    progress: int = Field(default=0, ge=0, le=100, description="Progress 0-100%")
    config_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Job configuration (checkpoint, bit_lengths, etc.)",
    )
    result_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Job results (metrics, index path, etc.)",
    )
    error_message: str | None = Field(default=None)
    pid: int | None = Field(default=None, description="System process ID")
    started_at: datetime | None = Field(default=None)
    ended_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    run: ExperimentRun = Relationship()


class OptunaStudy(SQLModel, table=True):
    """Optuna hyperparameter search study.

    Stores search space definition, optuna settings, and links to the
    config schema used for trial configs. The job system manages the
    subprocess lifecycle.
    """

    __tablename__ = "optuna_studies"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    config_schema_id: int | None = Field(default=None, foreign_key="config_schemas.id")
    base_config_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Fixed config values (non-search params)",
    )
    search_space_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Search space: {param_key: {type, low, high, ...}}",
    )
    n_trials: int = Field(default=20, ge=1)
    search_epochs: int = Field(default=5, ge=1, description="Epochs per trial")
    subset_ratio: float = Field(default=0.1, ge=0.01, le=1.0)
    pruner: str = Field(default="median", description="Optuna pruner: median|hyperband|none")
    objective_metric: str = Field(default="val/loss", description="Metric to optimize")
    direction: str = Field(default="maximize", description="maximize or minimize")
    status: JobStatus = Field(default=JobStatus.PENDING)
    best_trial_number: int | None = Field(default=None)
    best_value: float | None = Field(default=None)
    job_id: int | None = Field(default=None, foreign_key="jobs.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)

    # Relationships
    config_schema: ConfigSchema | None = Relationship()
    trials: list["OptunaTrialResult"] = Relationship(back_populates="study")


class OptunaTrialResult(SQLModel, table=True):
    """Result of a single Optuna trial."""

    __tablename__ = "optuna_trial_results"

    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="optuna_studies.id", index=True)
    trial_number: int = Field(ge=0)
    params_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Hyperparameters sampled for this trial",
    )
    objective_value: float | None = Field(default=None)
    status: TrialStatus = Field(default=TrialStatus.RUNNING)
    duration_seconds: float | None = Field(default=None)
    intermediate_values_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Intermediate objective values {step: value}",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    study: OptunaStudy = Relationship(back_populates="trials")


class QueueEntry(SQLModel, table=True):
    """Experiment queue entry for sequential auto-execution.

    Experiments are queued with a position (ordering). The queue scheduler
    polls for free GPU slots and auto-starts the next waiting entry.
    """

    __tablename__ = "queue_entries"

    id: int | None = Field(default=None, primary_key=True)
    experiment_config_id: int = Field(foreign_key="experiment_configs.id", index=True)
    position: int = Field(default=0, description="Queue position (lower = earlier)")
    status: QueueStatus = Field(default=QueueStatus.WAITING)
    run_id: int | None = Field(
        default=None,
        foreign_key="experiment_runs.id",
        description="Created run when started",
    )
    error_message: str | None = Field(default=None)
    added_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)

    # Relationships
    experiment_config: ExperimentConfig = Relationship()
    run: ExperimentRun | None = Relationship()


class DatasetDefinition(SQLModel, table=True):
    """Registered dataset for training.

    Tracks dataset location, JSONL readiness, and prepare job state.
    Status is computed dynamically from file system checks.
    """

    __tablename__ = "dataset_definitions"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True, description="Unique slug (e.g. coco, coco_ko)")
    name: str = Field(description="Display name")
    description: str = Field(default="")
    data_root: str = Field(default="", description="Path to image directory (relative to DATA_DIR)")
    raw_path: str = Field(
        default="",
        description="Path to raw annotations (relative to DATA_DIR)",
    )
    jsonl_path: str = Field(
        default="",
        description="Path to prepared JSONL file (relative to DATA_DIR)",
    )
    raw_format: str = Field(
        default="coco_karpathy",
        description="Format of raw data: coco_karpathy, jsonl_copy, custom",
    )
    entry_count: int | None = Field(default=None, description="Cached JSONL entry count")
    size_bytes: int | None = Field(default=None, description="Cached JSONL file size")
    prepare_job_id: int | None = Field(
        default=None,
        foreign_key="jobs.id",
        description="Active prepare job ID",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
