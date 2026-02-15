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


class GitLastCommit(BaseModel):
    """Git last commit info."""

    hash: str | None = None
    message: str | None = None
    date: str | None = None


class StructureInfo(BaseModel):
    """Detected project directory structure."""

    has_src: bool = False
    has_tests: bool = False
    has_docker: bool = False
    main_dirs: list[str] = Field(default_factory=list)


class ScanResponse(BaseModel):
    """Response from scanning a project directory."""

    exists: bool
    is_git: bool = False
    git_url: str | None = None
    git_branch: str | None = None
    git_last_commit: GitLastCommit | None = None
    python_env: PythonEnvInfo | None = None
    configs: list[ConfigFileInfo] = Field(default_factory=list)
    scripts: ScriptFiles = Field(default_factory=ScriptFiles)
    structure: StructureInfo | None = None
    requirements: list[str] = Field(default_factory=list)
    suggested_train_command: str | None = None
    suggested_eval_command: str | None = None


# ---------------------------------------------------------------------------
# Clone schemas
# ---------------------------------------------------------------------------


class CloneRequest(BaseModel):
    """Request to clone a GitHub repository."""

    git_url: str = Field(min_length=1)
    branch: str = Field(default="main")
    token_id: int | None = None
    subdirectory: str = ""


class CloneStatusResponse(BaseModel):
    """Status of a clone job."""

    job_id: str
    status: str  # started, cloning, scanning, completed, failed
    progress: str | None = None
    local_path: str | None = None
    scan_result: ScanResponse | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Filesystem browse schemas
# ---------------------------------------------------------------------------


class FileBrowseEntry(BaseModel):
    """Single entry in a filesystem browse response."""

    name: str
    type: str  # "dir" or "file"
    size: int = 0
    modified: str | None = None


class FileBrowseResponse(BaseModel):
    """Response for filesystem browse."""

    path: str
    entries: list[FileBrowseEntry]


# ---------------------------------------------------------------------------
# Upload schemas
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    """Response after file upload."""

    local_path: str
    files_saved: list[str]
    scan_result: ScanResponse | None = None


# ---------------------------------------------------------------------------
# Git credential schemas
# ---------------------------------------------------------------------------


class GitCredentialCreate(BaseModel):
    """Schema for creating a git credential."""

    name: str = Field(min_length=1)
    provider: str = Field(default="github")
    token: str = Field(min_length=1)


class GitCredentialResponse(BaseModel):
    """Schema for git credential response (token masked)."""

    id: int
    name: str
    provider: str
    token_masked: str
    created_at: datetime

    class Config:
        from_attributes = True


class GitCredentialListResponse(BaseModel):
    """List of git credentials."""

    credentials: list[GitCredentialResponse]


# ---------------------------------------------------------------------------
# Template schemas
# ---------------------------------------------------------------------------


class TemplateTask(BaseModel):
    """A task available within a template framework."""

    id: str
    name: str
    description: str = ""


class TemplateInfo(BaseModel):
    """A project template definition."""

    id: str
    framework: str
    name: str
    description: str = ""
    tasks: list[TemplateTask] = Field(default_factory=list)


class TemplateConfigSchema(BaseModel):
    """Config schema for a template."""

    template_id: str
    task_id: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CRUD schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    """Schema for creating a project."""

    name: str = Field(min_length=1)
    source_type: str = Field(default="local")
    path: str = Field(min_length=1)
    git_url: str | None = None
    git_branch: str | None = None
    git_token_id: int | None = None
    template_type: str | None = None
    template_task: str | None = None
    template_model: str | None = None
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
    source_type: str
    path: str
    git_url: str | None
    git_branch: str | None
    git_token_id: int | None
    template_type: str | None
    template_task: str | None
    template_model: str | None
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
            source_type=model.source_type,
            path=model.path,
            git_url=model.git_url,
            git_branch=model.git_branch,
            git_token_id=model.git_token_id,
            template_type=model.template_type,
            template_task=model.template_task,
            template_model=model.template_model,
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
