"""Per-project Python virtual environment manager.

Manages isolated venvs for ML projects so their dependencies
(PyTorch, transformers, etc.) don't conflict with the hub backend.
Uses uv for fast venv creation and package installation.
"""

import asyncio
import hashlib
import logging
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)


class ProjectEnvManager:
    """Manages per-ML-project Python virtual environments."""

    def __init__(self) -> None:
        self._base_dir = Path(settings.VENVS_DIR)
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            # /data/venvs not writable outside Docker — that's fine
            logger.debug("Cannot create venvs dir %s (expected outside Docker)", self._base_dir)

    def _project_hash(self, project_path: str) -> str:
        """Stable short hash of the project path for directory naming."""
        return hashlib.sha256(project_path.encode()).hexdigest()[:16]

    def _venv_dir(self, project_path: str) -> Path:
        """Return the venv directory for a project."""
        return self._base_dir / self._project_hash(project_path)

    def get_python(self, project_path: str) -> str:
        """Return the Python interpreter path for a project's venv."""
        return str(self._venv_dir(project_path) / "bin" / "python")

    def _deps_hash(self, project_path: str) -> str:
        """Hash dependency files to detect changes.

        Checks requirements.txt, pyproject.toml, and lock files.
        Returns a combined hash of all found dependency files.
        """
        dep_files = [
            "requirements.txt",
            "pyproject.toml",
            "uv.lock",
            "poetry.lock",
            "requirements-lock.txt",
        ]
        hasher = hashlib.sha256()
        found_any = False

        for name in dep_files:
            path = Path(project_path) / name
            if path.exists():
                hasher.update(path.read_bytes())
                found_any = True

        if not found_any:
            return ""

        return hasher.hexdigest()

    def _read_marker(self, project_path: str) -> str:
        """Read the stored deps hash marker for a venv."""
        marker = self._venv_dir(project_path) / ".deps_hash"
        if marker.exists():
            return marker.read_text().strip()
        return ""

    def _write_marker(self, project_path: str, deps_hash: str) -> None:
        """Write the deps hash marker after successful setup."""
        marker = self._venv_dir(project_path) / ".deps_hash"
        marker.write_text(deps_hash)

    async def _run(self, cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
        """Run a subprocess and return (returncode, combined output)."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
        stdout, _ = await process.communicate()
        return process.returncode or 0, stdout.decode(errors="replace")

    async def setup_project(self, project_path: str) -> str:
        """Set up a venv for the project if needed.

        1. Hash dependency files to check if venv is up-to-date
        2. If venv exists and deps haven't changed, skip (fast path)
        3. Otherwise, create venv with uv and install dependencies

        Args:
            project_path: Absolute path to the ML project directory.

        Returns:
            Path to the Python interpreter in the project's venv.

        Raises:
            RuntimeError: If venv creation or dependency installation fails.
            FileNotFoundError: If no dependency files found in project.
        """
        project = Path(project_path)
        if not project.is_dir():
            raise FileNotFoundError(f"Project directory not found: {project_path}")

        venv_dir = self._venv_dir(project_path)
        python_path = self.get_python(project_path)

        # Check deps hash for cache hit
        current_hash = self._deps_hash(project_path)
        if not current_hash:
            raise FileNotFoundError(
                f"No dependency files (requirements.txt / pyproject.toml) "
                f"found in {project_path}"
            )

        stored_hash = self._read_marker(project_path)
        if venv_dir.exists() and stored_hash == current_hash:
            logger.info(
                "Venv for %s is up-to-date (hash=%s…), skipping setup",
                project_path,
                current_hash[:8],
            )
            return python_path

        # Create or recreate venv
        logger.info("Setting up venv for %s at %s", project_path, venv_dir)

        rc, output = await self._run(["uv", "venv", str(venv_dir), "--python", "3.12"])
        if rc != 0:
            raise RuntimeError(f"Failed to create venv: {output}")

        # Install dependencies
        has_pyproject = (project / "pyproject.toml").exists()
        has_requirements = (project / "requirements.txt").exists()

        if has_pyproject:
            # Use uv pip install with the project's pyproject.toml
            rc, output = await self._run(
                ["uv", "pip", "install", "--python", python_path, "-e", str(project)],
            )
            if rc != 0:
                # Fallback: try non-editable install
                rc, output = await self._run(
                    ["uv", "pip", "install", "--python", python_path, str(project)],
                )
                if rc != 0:
                    raise RuntimeError(f"Failed to install from pyproject.toml: {output}")
        elif has_requirements:
            rc, output = await self._run(
                [
                    "uv", "pip", "install",
                    "--python", python_path,
                    "-r", str(project / "requirements.txt"),
                ],
            )
            if rc != 0:
                raise RuntimeError(f"Failed to install from requirements.txt: {output}")

        # Write marker on success
        self._write_marker(project_path, current_hash)
        logger.info("Venv setup complete for %s", project_path)

        return python_path

    def is_ready(self, project_path: str) -> bool:
        """Check if a project's venv exists and is set up."""
        venv_dir = self._venv_dir(project_path)
        python = Path(self.get_python(project_path))
        return venv_dir.exists() and python.exists()


# Global instance
env_manager = ProjectEnvManager()
