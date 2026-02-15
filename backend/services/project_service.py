"""Business logic for project management and directory scanning."""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from backend.models.experiment import ExperimentConfig, Project
from backend.schemas.project import (
    ConfigFileInfo,
    ProjectCreate,
    ProjectUpdate,
    PythonEnvInfo,
    ScanResponse,
    ScriptFiles,
)
from shared.schemas import ProjectStatus

logger = logging.getLogger(__name__)

# Config file extensions to detect
CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml"}

# Script patterns for classification
TRAIN_PATTERNS = {"train", "training", "fit"}
EVAL_PATTERNS = {"eval", "evaluate", "evaluation", "test", "infer", "inference"}


class ProjectService:
    """Service for managing projects."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def list_projects(
        self,
        skip: int = 0,
        limit: int = 100,
        status: ProjectStatus | None = None,
    ) -> list[Project]:
        query = select(Project)
        if status is not None:
            query = query.where(Project.status == status)
        query = query.offset(skip).limit(limit).order_by(Project.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_projects(self, status: ProjectStatus | None = None) -> int:
        query = select(func.count()).select_from(Project)
        if status is not None:
            query = query.where(Project.status == status)
        result = await self.session.execute(query)
        count = result.scalar()
        return count if count is not None else 0

    async def get_project(self, project_id: int) -> Project | None:
        result = await self.session.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def create_project(self, data: ProjectCreate) -> Project:
        project = Project(
            name=data.name,
            path=data.path,
            git_url=data.git_url,
            description=data.description,
            project_type=data.project_type,
            train_command_template=data.train_command_template,
            eval_command_template=data.eval_command_template,
            config_dir=data.config_dir,
            config_format=data.config_format,
            checkpoint_dir=data.checkpoint_dir,
            python_env=data.python_env,
            env_path=data.env_path,
            status=ProjectStatus.READY,
            detected_configs=data.detected_configs,
            detected_scripts=data.detected_scripts,
            tags=data.tags,
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def update_project(self, project_id: int, updates: ProjectUpdate) -> Project | None:
        project = await self.get_project(project_id)
        if not project:
            return None

        update_data = updates.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(project, key, value)

        project.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete_project(self, project_id: int) -> bool:
        project = await self.get_project(project_id)
        if not project:
            return False
        await self.session.delete(project)
        await self.session.commit()
        return True

    async def count_experiments_for_project(self, project_id: int) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(ExperimentConfig)
            .where(ExperimentConfig.project_id == project_id)
        )
        count = result.scalar()
        return count if count is not None else 0

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    async def rescan_project(self, project_id: int) -> Project | None:
        """Re-scan an existing project and update detected files."""
        project = await self.get_project(project_id)
        if not project:
            return None

        scan = scan_directory(project.path)
        project.detected_configs = [c.model_dump() for c in scan.configs]
        project.detected_scripts = scan.scripts.model_dump()
        if scan.git_url and not project.git_url:
            project.git_url = scan.git_url
        project.status = ProjectStatus.READY
        project.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(project)
        return project


# ======================================================================
# Standalone scan functions (no DB dependency)
# ======================================================================


def scan_directory(path: str) -> ScanResponse:
    """Scan a project directory and return detected information."""
    root = Path(path)
    if not root.exists() or not root.is_dir():
        return ScanResponse(exists=False)

    is_git = (root / ".git").is_dir()
    git_url: str | None = None
    git_branch: str | None = None

    if is_git:
        git_url = _get_git_remote(root)
        git_branch = _get_git_branch(root)

    python_env = _detect_python_env(root)
    configs = _find_configs(root)
    scripts = _find_scripts(root)

    suggested_train = _suggest_train_command(root, python_env, scripts)
    suggested_eval = _suggest_eval_command(root, python_env, scripts)

    return ScanResponse(
        exists=True,
        is_git=is_git,
        git_url=git_url,
        git_branch=git_branch,
        python_env=python_env,
        configs=configs,
        scripts=scripts,
        suggested_train_command=suggested_train,
        suggested_eval_command=suggested_eval,
    )


def _get_git_remote(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(root),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _get_git_branch(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(root),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _detect_python_env(root: Path) -> PythonEnvInfo:
    """Detect Python environment type from project files."""
    # Check for uv (pyproject.toml with uv indicators)
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        content = ""
        try:
            content = pyproject.read_text(errors="ignore")
        except OSError:
            pass

        if "uv" in content or (root / "uv.lock").exists():
            venv_path = root / ".venv"
            return PythonEnvInfo(
                type="uv",
                indicator="pyproject.toml",
                venv_exists=venv_path.is_dir(),
                venv_path=".venv" if venv_path.is_dir() else None,
            )

    # Check for conda
    env_yml = root / "environment.yml"
    if env_yml.exists():
        return PythonEnvInfo(
            type="conda",
            indicator="environment.yml",
            venv_exists=False,
        )

    # Check for venv / virtualenv
    for venv_name in [".venv", "venv", "env"]:
        venv_dir = root / venv_name
        if venv_dir.is_dir() and (venv_dir / "bin" / "python").exists():
            return PythonEnvInfo(
                type="venv",
                indicator=venv_name,
                venv_exists=True,
                venv_path=venv_name,
            )

    # Check for requirements.txt (pip)
    if (root / "requirements.txt").exists():
        return PythonEnvInfo(
            type="pip",
            indicator="requirements.txt",
            venv_exists=False,
        )

    # Check for pyproject.toml without uv
    if pyproject.exists():
        return PythonEnvInfo(
            type="pip",
            indicator="pyproject.toml",
            venv_exists=False,
        )

    return PythonEnvInfo(type="system", indicator="")


def _find_configs(root: Path) -> list[ConfigFileInfo]:
    """Find config files in common locations."""
    configs: list[ConfigFileInfo] = []

    # Search config directories
    config_dirs = ["configs", "config", "conf", "cfg"]
    for dir_name in config_dirs:
        config_dir = root / dir_name
        if config_dir.is_dir():
            for f in sorted(config_dir.rglob("*")):
                if f.is_file() and f.suffix in CONFIG_EXTENSIONS:
                    rel = str(f.relative_to(root))
                    fmt = f.suffix.lstrip(".")
                    if fmt in ("yml",):
                        fmt = "yaml"
                    try:
                        size = f.stat().st_size
                    except OSError:
                        size = 0
                    configs.append(ConfigFileInfo(path=rel, format=fmt, size=size))

    # Also check root-level config files
    for f in sorted(root.iterdir()):
        if f.is_file() and f.suffix in CONFIG_EXTENSIONS and f.stem.startswith("config"):
            rel = str(f.relative_to(root))
            fmt = f.suffix.lstrip(".")
            if fmt in ("yml",):
                fmt = "yaml"
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            if not any(c.path == rel for c in configs):
                configs.append(ConfigFileInfo(path=rel, format=fmt, size=size))

    return configs


def _find_scripts(root: Path) -> ScriptFiles:
    """Find Python scripts and classify them."""
    train_scripts: list[str] = []
    eval_scripts: list[str] = []
    other_scripts: list[str] = []

    # Directories to skip
    skip_dirs = {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "node_modules",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".eggs",
    }

    for f in sorted(root.rglob("*.py")):
        # Skip hidden/venv dirs
        parts = f.relative_to(root).parts
        if any(p in skip_dirs or p.startswith(".") for p in parts[:-1]):
            continue

        rel = str(f.relative_to(root))
        stem = f.stem.lower()

        if any(p in stem for p in TRAIN_PATTERNS):
            train_scripts.append(rel)
        elif any(p in stem for p in EVAL_PATTERNS):
            eval_scripts.append(rel)
        elif stem not in ("__init__", "setup", "conftest"):
            # Only include top-level or scripts/ directory scripts as "other"
            depth = len(parts)
            if depth <= 2:
                other_scripts.append(rel)

    return ScriptFiles(
        train=train_scripts,
        eval=eval_scripts,
        other=other_scripts,
    )


def _suggest_train_command(root: Path, env: PythonEnvInfo, scripts: ScriptFiles) -> str | None:
    """Suggest a training command based on detected environment and scripts."""
    if not scripts.train:
        return None

    script = scripts.train[0]
    prefix = _env_prefix(env)
    return f"{prefix}python {script} --config {{config_path}}"


def _suggest_eval_command(root: Path, env: PythonEnvInfo, scripts: ScriptFiles) -> str | None:
    """Suggest an evaluation command."""
    if not scripts.eval:
        return None

    script = scripts.eval[0]
    prefix = _env_prefix(env)
    return f"{prefix}python {script} --checkpoint {{checkpoint_path}} --config {{config_path}}"


def _env_prefix(env: PythonEnvInfo) -> str:
    """Get command prefix for Python environment."""
    if env.type == "uv":
        return "uv run "
    if env.type == "conda":
        return "conda run -n base "
    return ""


def get_git_info(project_path: str) -> dict[str, Any]:
    """Get detailed git info for a project directory."""
    root = Path(project_path)
    if not (root / ".git").is_dir():
        return {}

    info: dict[str, Any] = {}

    try:
        # Branch
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(root),
        )
        if r.returncode == 0:
            info["branch"] = r.stdout.strip()

        # Remote URL
        r = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(root),
        )
        if r.returncode == 0:
            info["remote_url"] = r.stdout.strip()

        # Last commit
        r = subprocess.run(
            ["git", "log", "-1", "--format=%H%n%s%n%ai"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(root),
        )
        if r.returncode == 0:
            lines = r.stdout.strip().split("\n")
            if len(lines) >= 3:
                info["last_commit_hash"] = lines[0][:12]
                info["last_commit_message"] = lines[1]
                info["last_commit_date"] = lines[2]

        # Dirty check
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(root),
        )
        if r.returncode == 0:
            info["dirty"] = bool(r.stdout.strip())

    except Exception:
        logger.debug("Git info collection failed for %s", project_path, exc_info=True)

    return info


def read_config_file(project_path: str, config_rel_path: str) -> str | None:
    """Read the contents of a config file within a project."""
    root = Path(project_path)
    config_path = root / config_rel_path

    # Security: ensure the resolved path is within the project directory
    try:
        config_path = config_path.resolve()
        root_resolved = root.resolve()
        if not str(config_path).startswith(str(root_resolved)):
            return None
    except (OSError, ValueError):
        return None

    if not config_path.is_file():
        return None

    try:
        return config_path.read_text(errors="replace")
    except OSError:
        return None
