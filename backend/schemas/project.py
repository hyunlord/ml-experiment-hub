"""Project schemas for API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas import ProjectStatus


# ---------------------------------------------------------------------------
# Scan schemas
# ---------------------------------------------------------------------------


class ScanRequest(BaseModel):
    """Request to scan a project directory."""

    path: str = Field(min_length=1, description="Absolute path to project directory")


class PythonEnvInfo(BaseModel):
    """Detected Python environment info."""

    type: str = Field(description="uv, venv, conda, pip, system")
    indicator: str = Field(default="", description="File that triggered detection")
    venv_exists: bool = Field(default=False)
    venv_path: str | None = Field(default=None)


class ConfigFileInfo(BaseModel):
    """Detected config file."""

    path: str
    format: str
    size: int


class ScriptFiles(BaseModel):
    """Detected script files grouped by category."""

    train: list[str] = Field(default_factory=list)
    eval: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)


class ScanResponse(BaseModel):
    """Response from scanning a project directory."""

    exists: bool
    is_git: bool = False
    git_url: str | None = None
    git_branch: str | None = None
    python_env: PythonEnvInfo | None = None
    configs: list[ConfigFileInfo] = Field(default_factory=list)
    scripts: ScriptFiles = Field(default_factory=ScriptFiles)
    suggested_train_command: str | None = None
    suggested_eval_command: str | None = None


# ---------------------------------------------------------------------------
# CRUD schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    """Schema for creating a project."""

    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    git_url: str | None = None
    description: str = ""
    project_type: str = "custom"
    train_command_template: str = "python train.py --config {config_path}"
    eval_command_template: str | None = None
    config_dir: str = "configs/"
    config_format: str = "yaml"
    checkpoint_dir: str = "checkpoints/"
    python_env: str = "system"
    env_path: str | None = None
    detected_configs: list[dict[str, Any]] = Field(default_factory=list)
    detected_scripts: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: str | None = None
    description: str | None = None
    project_type: str | None = None
    train_command_template: str | None = None
    eval_command_template: str | None = None
    config_dir: str | None = None
    config_format: str | None = None
    checkpoint_dir: str | None = None
    python_env: str | None = None
    env_path: str | None = None
    tags: list[str] | None = None


class ProjectResponse(BaseModel):
    """Schema for project response."""

    id: int
    name: str
    path: str
    git_url: str | None
    description: str
    project_type: str
    train_command_template: str
    eval_command_template: str | None
    config_dir: str
    config_format: str
    checkpoint_dir: str
    python_env: str
    env_path: str | None
    status: ProjectStatus
    detected_configs: list[dict[str, Any]]
    detected_scripts: dict[str, Any]
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    experiment_count: int = 0

    class Config:
        from_attributes = True

    @classmethod
    def from_model(cls, model: Any, experiment_count: int = 0) -> "ProjectResponse":
        return cls(
            id=model.id,
            name=model.name,
            path=model.path,
            git_url=model.git_url,
            description=model.description,
            project_type=model.project_type,
            train_command_template=model.train_command_template,
            eval_command_template=model.eval_command_template,
            config_dir=model.config_dir,
            config_format=model.config_format,
            checkpoint_dir=model.checkpoint_dir,
            python_env=model.python_env,
            env_path=model.env_path,
            status=model.status,
            detected_configs=model.detected_configs or [],
            detected_scripts=model.detected_scripts or {},
            tags=model.tags or [],
            created_at=model.created_at,
            updated_at=model.updated_at,
            experiment_count=experiment_count,
        )


class ProjectListResponse(BaseModel):
    """Schema for project list response."""

    projects: list[ProjectResponse]
    total: int


class ConfigContentResponse(BaseModel):
    """Response for reading a config file's contents."""

    path: str
    content: str
    format: str


class GitInfoResponse(BaseModel):
    """Git information for a project."""

    branch: str | None = None
    remote_url: str | None = None
    last_commit_hash: str | None = None
    last_commit_message: str | None = None
    last_commit_date: str | None = None
    dirty: bool = False
