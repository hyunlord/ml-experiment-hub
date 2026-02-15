"""Async GitHub clone service with job tracking."""

import asyncio
import hashlib
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.services.project_service import scan_directory

logger = logging.getLogger(__name__)

# In-memory job store (lost on restart, acceptable for MVP)
_clone_jobs: dict[str, dict[str, Any]] = {}

# Clone timeout in seconds (10 minutes)
_CLONE_TIMEOUT = 600


def _parse_git_error(stderr: str) -> str:
    """Parse git stderr into a user-friendly error message."""
    lower = stderr.lower()

    if "repository not found" in lower or "does not appear to be a git repository" in lower:
        return "Repository not found. Please check the URL."
    if "authentication failed" in lower or "could not read username" in lower:
        return "Authentication failed. If this is a private repo, please configure a token."
    if "could not resolve host" in lower:
        return "Network error. Please check your internet connection."
    if "remote branch" in lower and "not found" in lower:
        return "Branch not found. Please check the branch name."
    if "already exists and is not an empty directory" in lower:
        return "Target directory already exists. Please try again."
    if "permission denied" in lower:
        return "Permission denied. Please check file system permissions."

    # Return cleaned stderr if no specific match (strip token URLs)
    cleaned = stderr.strip()
    # Remove token from any leaked URLs
    if "@github.com" in cleaned or "@gitlab.com" in cleaned:
        import re

        cleaned = re.sub(r"https://[^@]+@", "https://***@", cleaned)
    return cleaned or "Clone failed with an unknown error."


def _ensure_projects_dir() -> None:
    """Ensure PROJECTS_STORE_DIR exists."""
    Path(settings.PROJECTS_STORE_DIR).mkdir(parents=True, exist_ok=True)


async def start_clone(
    git_url: str,
    branch: str = "main",
    token: str | None = None,
    subdirectory: str = "",
) -> str:
    """Start an async clone job. Returns job_id."""
    # Pre-flight: check git is installed
    if not shutil.which("git"):
        job_id = f"clone_{uuid.uuid4().hex[:12]}"
        _clone_jobs[job_id] = {
            "status": "failed",
            "progress": None,
            "local_path": None,
            "scan_result": None,
            "error": ("git is not installed on the server. Please add 'git' to your Dockerfile."),
            "git_url": git_url,
            "branch": branch,
        }
        return job_id

    # Ensure projects directory exists
    _ensure_projects_dir()

    job_id = f"clone_{uuid.uuid4().hex[:12]}"

    # Derive target path: PROJECTS_STORE_DIR / repo_name_shorthash
    repo_name = git_url.rstrip("/").split("/")[-1].replace(".git", "")
    short_hash = hashlib.sha256(
        f"{git_url}:{branch}:{datetime.utcnow().isoformat()}".encode()
    ).hexdigest()[:8]
    target_path = str(Path(settings.PROJECTS_STORE_DIR) / f"{repo_name}_{short_hash}")

    _clone_jobs[job_id] = {
        "status": "started",
        "progress": None,
        "local_path": target_path,
        "scan_result": None,
        "error": None,
        "git_url": git_url,
        "branch": branch,
    }

    # Launch clone in background
    asyncio.create_task(_run_clone(job_id, git_url, branch, token, target_path))
    return job_id


def get_clone_status(job_id: str) -> dict[str, Any] | None:
    """Get the status of a clone job."""
    return _clone_jobs.get(job_id)


async def _run_clone(
    job_id: str,
    git_url: str,
    branch: str,
    token: str | None,
    target_path: str,
) -> None:
    """Run git clone as async subprocess."""
    job = _clone_jobs[job_id]

    try:
        # Ensure parent directory exists
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)

        # Build clone URL (inject token for private repos)
        clone_url = git_url
        if token and "github.com" in git_url:
            clone_url = git_url.replace("https://", f"https://{token}@")
        elif token and "gitlab.com" in git_url:
            clone_url = git_url.replace("https://", f"https://oauth2:{token}@")

        job["status"] = "cloning"
        job["progress"] = "Starting clone..."

        cmd = ["git", "clone", "--depth", "1", "--branch", branch, clone_url, target_path]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Read stderr for progress (git outputs progress to stderr)
        assert process.stderr is not None
        stderr_lines: list[str] = []
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            progress_text = line.decode(errors="replace").strip()
            if progress_text:
                stderr_lines.append(progress_text)
                job["progress"] = progress_text

        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=_CLONE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            process.kill()
            job["status"] = "failed"
            job["error"] = (
                "Clone timed out. The repository may be too large "
                "or the network connection is slow."
            )
            return

        if process.returncode != 0:
            stderr_remaining = await process.stderr.read()
            all_stderr = "\n".join(stderr_lines)
            if stderr_remaining:
                all_stderr += "\n" + stderr_remaining.decode(errors="replace").strip()
            job["status"] = "failed"
            job["error"] = _parse_git_error(all_stderr)
            return

        # Clone succeeded, now scan
        job["status"] = "scanning"
        job["progress"] = "Scanning project directory..."

        scan_result = scan_directory(target_path)
        job["scan_result"] = scan_result.model_dump()
        job["status"] = "completed"
        job["progress"] = "Done"

    except FileNotFoundError:
        # This catches the case where git binary disappears mid-execution
        logger.error("Clone job %s failed: git not found", job_id, exc_info=True)
        job["status"] = "failed"
        job["error"] = "git is not installed on the server. Please add 'git' to your Dockerfile."
    except Exception as e:
        logger.error("Clone job %s failed: %s", job_id, e, exc_info=True)
        job["status"] = "failed"
        job["error"] = _parse_git_error(str(e))
