"""initial: create all tables

Revision ID: 0001abcd0001
Revises:
Create Date: 2026-02-15 23:00:00.000000

Squashed from 4 incremental migrations into a single clean baseline
with all 15 tables. Safe for fresh deployments.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "0001abcd0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables."""

    # ── Independent tables (no FKs) ─────────────────────────────────────

    op.create_table(
        "git_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("git_credentials") as batch_op:
        batch_op.create_index(batch_op.f("ix_git_credentials_name"), ["name"])

    op.create_table(
        "config_schemas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("fields_schema", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("config_schemas") as batch_op:
        batch_op.create_index(batch_op.f("ix_config_schemas_name"), ["name"])

    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("host", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("auth_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("api_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_local", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("servers") as batch_op:
        batch_op.create_index(batch_op.f("ix_servers_name"), ["name"])

    # ── projects (FK → git_credentials) ─────────────────────────────────

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("git_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("git_branch", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("git_token_id", sa.Integer(), nullable=True),
        sa.Column("template_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("template_task", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("template_model", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("train_command_template", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("eval_command_template", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("config_dir", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("config_format", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("checkpoint_dir", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("python_env", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("env_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("REGISTERED", "CLONING", "SCANNING", "READY", "ERROR", name="projectstatus"),
            nullable=False,
        ),
        sa.Column("detected_configs", sa.JSON(), nullable=True),
        sa.Column("detected_scripts", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["git_token_id"], ["git_credentials.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("projects") as batch_op:
        batch_op.create_index(batch_op.f("ix_projects_name"), ["name"])

    # ── experiment_configs (FK → config_schemas, projects) ──────────────

    op.create_table(
        "experiment_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("config_schema_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED",
                name="experimentconfigstatus",
            ),
            nullable=False,
        ),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # Project snapshot (captured at experiment creation for reproducibility)
        sa.Column("project_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_git_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_git_branch", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_git_commit", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_git_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("project_git_dirty", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("project_python_env", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["config_schema_id"], ["config_schemas.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("experiment_configs") as batch_op:
        batch_op.create_index(batch_op.f("ix_experiment_configs_name"), ["name"])
        batch_op.create_index(batch_op.f("ix_experiment_configs_project_id"), ["project_id"])

    # ── experiment_runs (FK → experiment_configs) ───────────────────────

    op.create_table(
        "experiment_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_config_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="runstatus"),
            nullable=False,
        ),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("log_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("metrics_summary", sa.JSON(), nullable=True),
        sa.Column("checkpoint_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["experiment_config_id"], ["experiment_configs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("experiment_runs") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_experiment_runs_experiment_config_id"),
            ["experiment_config_id"],
        )

    # ── metric_logs (FK → experiment_runs) ──────────────────────────────

    op.create_table(
        "metric_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["experiment_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("metric_logs") as batch_op:
        batch_op.create_index(batch_op.f("ix_metric_logs_run_id"), ["run_id"])
        batch_op.create_index("ix_metric_logs_run_step", ["run_id", "step"])

    # ── system_stats (FK → experiment_runs) ─────────────────────────────

    op.create_table(
        "system_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("gpu_util", sa.Float(), nullable=True),
        sa.Column("gpu_memory_used", sa.Float(), nullable=True),
        sa.Column("gpu_memory_total", sa.Float(), nullable=True),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("ram_percent", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["experiment_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("system_stats") as batch_op:
        batch_op.create_index(batch_op.f("ix_system_stats_run_id"), ["run_id"])

    # ── jobs (FK → experiment_runs) ─────────────────────────────────────

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "job_type",
            sa.Enum("EVAL", "INDEX_BUILD", "OPTUNA_SEARCH", "DATASET_PREPARE", name="jobtype"),
            nullable=False,
        ),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="jobstatus"),
            nullable=False,
        ),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["experiment_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.create_index(batch_op.f("ix_jobs_run_id"), ["run_id"])

    # ── optuna_studies (FK → config_schemas, jobs) ──────────────────────

    op.create_table(
        "optuna_studies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("config_schema_id", sa.Integer(), nullable=True),
        sa.Column("base_config_json", sa.JSON(), nullable=True),
        sa.Column("search_space_json", sa.JSON(), nullable=True),
        sa.Column("n_trials", sa.Integer(), nullable=False),
        sa.Column("search_epochs", sa.Integer(), nullable=False),
        sa.Column("subset_ratio", sa.Float(), nullable=False),
        sa.Column("pruner", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("objective_metric", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("direction", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="jobstatus"),
            nullable=False,
        ),
        sa.Column("best_trial_number", sa.Integer(), nullable=True),
        sa.Column("best_value", sa.Float(), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["config_schema_id"], ["config_schemas.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("optuna_studies") as batch_op:
        batch_op.create_index(batch_op.f("ix_optuna_studies_name"), ["name"])

    # ── optuna_trial_results (FK → optuna_studies) ──────────────────────

    op.create_table(
        "optuna_trial_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("study_id", sa.Integer(), nullable=False),
        sa.Column("trial_number", sa.Integer(), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=True),
        sa.Column("objective_value", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("RUNNING", "COMPLETED", "PRUNED", "FAILED", name="trialstatus"),
            nullable=False,
        ),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("intermediate_values_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["optuna_studies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("optuna_trial_results") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_optuna_trial_results_study_id"), ["study_id"]
        )

    # ── queue_entries (FK → experiment_configs, experiment_runs) ─────────

    op.create_table(
        "queue_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_config_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("WAITING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="queuestatus"),
            nullable=False,
        ),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["experiment_config_id"], ["experiment_configs.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["experiment_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("queue_entries") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_queue_entries_experiment_config_id"),
            ["experiment_config_id"],
        )

    # ── dataset_definitions (FK → jobs) ─────────────────────────────────

    op.create_table(
        "dataset_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "dataset_type",
            sa.Enum("IMAGE_TEXT", "TEXT_ONLY", "IMAGE_ONLY", "TABULAR", "CUSTOM", name="datasettype"),
            nullable=False,
        ),
        sa.Column(
            "dataset_format",
            sa.Enum("JSONL", "CSV", "PARQUET", "HUGGINGFACE", "DIRECTORY", name="datasetformat"),
            nullable=False,
        ),
        sa.Column("data_root", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("raw_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("jsonl_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("raw_format", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "split_method",
            sa.Enum("RATIO", "FILE", "FIELD", "CUSTOM", "NONE", name="splitmethod"),
            nullable=False,
        ),
        sa.Column("splits_config", sa.JSON(), nullable=True),
        sa.Column("entry_count", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("is_seed", sa.Boolean(), nullable=False),
        sa.Column("prepare_job_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["prepare_job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("dataset_definitions") as batch_op:
        batch_op.create_index(batch_op.f("ix_dataset_definitions_key"), ["key"], unique=True)

    # ── system_history (FK → servers) ───────────────────────────────────

    op.create_table(
        "system_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("gpu_util", sa.Float(), nullable=True),
        sa.Column("gpu_memory_percent", sa.Float(), nullable=True),
        sa.Column("gpu_temperature", sa.Float(), nullable=True),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("ram_percent", sa.Float(), nullable=True),
        sa.Column("disk_percent", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("system_history") as batch_op:
        batch_op.create_index(batch_op.f("ix_system_history_server_id"), ["server_id"])
        batch_op.create_index("ix_system_history_ts", ["timestamp"])


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table("system_history")
    op.drop_table("dataset_definitions")
    op.drop_table("queue_entries")
    op.drop_table("optuna_trial_results")
    op.drop_table("optuna_studies")
    op.drop_table("jobs")
    op.drop_table("system_stats")
    op.drop_table("metric_logs")
    op.drop_table("experiment_runs")
    op.drop_table("experiment_configs")
    op.drop_table("projects")
    op.drop_table("servers")
    op.drop_table("config_schemas")
    op.drop_table("git_credentials")
