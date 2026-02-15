"""Filesystem browse API for project path selection."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.config import settings
from backend.schemas.project import FileBrowseEntry, FileBrowseResponse

router = APIRouter(prefix="/api/filesystem", tags=["filesystem"])

# Allowed root paths for browsing (security)
ALLOWED_ROOTS = ["/home", "/data", "/tmp", "/opt"]


def _is_path_allowed(path: str) -> bool:
    """Check if a path is within allowed directories."""
    resolved = str(Path(path).resolve())
    store_dir = str(Path(settings.PROJECTS_STORE_DIR).resolve())

    # Always allow PROJECTS_STORE_DIR
    if resolved.startswith(store_dir):
        return True

    # Check allowed roots
    for root in ALLOWED_ROOTS:
        if resolved.startswith(root):
            return True

    return False


@router.get("/browse", response_model=FileBrowseResponse)
async def browse_directory(
    path: str = Query(default="", description="Directory path to browse"),
) -> FileBrowseResponse:
    """Browse a directory on the server filesystem."""
    # Default to PROJECTS_STORE_DIR
    if not path:
        path = settings.PROJECTS_STORE_DIR

    # Security check
    if not _is_path_allowed(path):
        raise HTTPException(
            status_code=403,
            detail="Access to this path is not allowed",
        )

    target = Path(path)
    if not target.exists():
        # Create PROJECTS_STORE_DIR if it doesn't exist
        if str(target.resolve()) == str(Path(settings.PROJECTS_STORE_DIR).resolve()):
            target.mkdir(parents=True, exist_ok=True)
        else:
            raise HTTPException(status_code=404, detail="Directory not found")

    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    entries: list[FileBrowseEntry] = []
    try:
        for item in sorted(target.iterdir()):
            # Skip hidden files
            if item.name.startswith("."):
                continue

            try:
                stat = item.stat()
                modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
                entry_type = "dir" if item.is_dir() else "file"
                size = stat.st_size if item.is_file() else 0
            except OSError:
                continue

            entries.append(
                FileBrowseEntry(
                    name=item.name,
                    type=entry_type,
                    size=size,
                    modified=modified,
                )
            )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return FileBrowseResponse(path=str(target.resolve()), entries=entries)
