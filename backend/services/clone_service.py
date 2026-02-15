"""Async GitHub clone service with job tracking."""

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.services.project_service import scan_directory

logger = logging.getLogger(__name__)

# In-memory job store (lost on restart, acceptable for MVP)
_clone_jobs: dict[str, dict[str, Any]] = {}


async def start_clone(
    git_url: str,
    branch: str = "main",
    token: str | None = None,
    subdirectory: str = "",
) -> str:
    """Start an async clone job. Returns job_id."""
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
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            progress_text = line.decode(errors="replace").strip()
            if progress_text:
                job["progress"] = progress_text

        await process.wait()

        if process.returncode != 0:
            stderr_remaining = await process.stderr.read()
            error_msg = stderr_remaining.decode(errors="replace").strip()
            job["status"] = "failed"
            job["error"] = error_msg or f"git clone exited with code {process.returncode}"
            return

        # Clone succeeded, now scan
        job["status"] = "scanning"
        job["progress"] = "Scanning project directory..."

        scan_result = scan_directory(target_path)
        job["scan_result"] = scan_result.model_dump()
        job["status"] = "completed"
        job["progress"] = "Done"

    except Exception as e:
        logger.error("Clone job %s failed: %s", job_id, e, exc_info=True)
        job["status"] = "failed"
        job["error"] = str(e)
