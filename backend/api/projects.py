"""REST API endpoints for project management."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.database import get_session
from backend.schemas.project import (
    CloneRequest,
    CloneStatusResponse,
    ConfigContentResponse,
    GitInfoResponse,
    ParseConfigRequest,
    ParseConfigResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    ScanRequest,
    ScanResponse,
    UploadResponse,
)
from backend.services.clone_service import get_clone_status, start_clone
from backend.services.project_service import (
    ProjectService,
    get_git_info,
    read_config_file,
    scan_directory,
)
from shared.schemas import ProjectStatus

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    status: ProjectStatus | None = None,
) -> ProjectListResponse:
    """List registered projects."""
    service = ProjectService(session)
    projects = await service.list_projects(skip=skip, limit=limit, status=status)
    total = await service.count_projects(status=status)

    responses = []
    for p in projects:
        exp_count = await service.count_experiments_for_project(p.id)  # type: ignore[arg-type]
        responses.append(ProjectResponse.from_model(p, experiment_count=exp_count))

    return ProjectListResponse(projects=responses, total=total)


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectResponse:
    """Register a new project."""
    service = ProjectService(session)
    project = await service.create_project(data)
    return ProjectResponse.from_model(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectResponse:
    """Get project by ID."""
    service = ProjectService(session)
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    exp_count = await service.count_experiments_for_project(project_id)
    return ProjectResponse.from_model(project, experiment_count=exp_count)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    updates: ProjectUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectResponse:
    """Update project settings."""
    service = ProjectService(session)
    project = await service.update_project(project_id, updates)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    exp_count = await service.count_experiments_for_project(project_id)
    return ProjectResponse.from_model(project, experiment_count=exp_count)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete a project."""
    service = ProjectService(session)
    deleted = await service.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/scan", response_model=ScanResponse)
async def scan_project_directory(
    body: ScanRequest,
) -> ScanResponse:
    """Scan a directory and return detected project info."""
    return scan_directory(body.path)


@router.post("/upload", response_model=UploadResponse)
async def upload_project_files(
    files: list[UploadFile] = File(...),
    project_name: str = Query(default="uploaded_project"),
) -> UploadResponse:
    """Upload project files (train scripts, configs) to the server."""
    import hashlib
    from datetime import datetime as dt

    short_hash = hashlib.sha256(f"{project_name}:{dt.utcnow().isoformat()}".encode()).hexdigest()[
        :8
    ]
    target_dir = Path(settings.PROJECTS_STORE_DIR) / f"{project_name}_{short_hash}"
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_files: list[str] = []
    for f in files:
        if not f.filename:
            continue
        # Security: prevent path traversal
        safe_name = Path(f.filename).name
        dest = target_dir / safe_name
        content = await f.read()
        dest.write_bytes(content)
        saved_files.append(safe_name)

    # Auto-scan the uploaded directory
    scan_result = scan_directory(str(target_dir))

    return UploadResponse(
        local_path=str(target_dir),
        files_saved=saved_files,
        scan_result=scan_result,
    )


@router.post("/clone", response_model=CloneStatusResponse)
async def clone_repository(
    body: CloneRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CloneStatusResponse:
    """Clone a GitHub repository and scan it."""
    # If token_id provided, fetch the token
    token: str | None = None
    if body.token_id:
        from backend.models.experiment import GitCredential
        from sqlmodel import select

        result = await session.execute(
            select(GitCredential).where(GitCredential.id == body.token_id)
        )
        cred = result.scalar_one_or_none()
        if not cred:
            raise HTTPException(status_code=404, detail="Git credential not found")
        token = cred.token

    job_id = await start_clone(
        git_url=body.git_url,
        branch=body.branch,
        token=token,
        subdirectory=body.subdirectory,
    )
    return CloneStatusResponse(job_id=job_id, status="started")


@router.get("/clone/{job_id}", response_model=CloneStatusResponse)
async def get_clone_job_status(job_id: str) -> CloneStatusResponse:
    """Get the status of a clone job."""
    status = get_clone_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Clone job not found")

    scan_result = None
    if status.get("scan_result"):
        from backend.schemas.project import ScanResponse

        scan_result = ScanResponse(**status["scan_result"])

    return CloneStatusResponse(
        job_id=job_id,
        status=status["status"],
        progress=status.get("progress"),
        local_path=status.get("local_path"),
        scan_result=scan_result,
        error=status.get("error"),
    )


@router.post("/{project_id}/rescan", response_model=ProjectResponse)
async def rescan_project(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectResponse:
    """Re-scan project directory and update detected files."""
    service = ProjectService(session)
    project = await service.rescan_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    exp_count = await service.count_experiments_for_project(project_id)
    return ProjectResponse.from_model(project, experiment_count=exp_count)


@router.post("/{project_id}/pull")
async def pull_project(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Run git pull on a GitHub-sourced project."""
    import asyncio

    service = ProjectService(session)
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.source_type != "github":
        raise HTTPException(status_code=400, detail="Git pull only available for GitHub projects")

    project_path = Path(project.path)
    if not (project_path / ".git").is_dir():
        raise HTTPException(status_code=400, detail="Not a git repository")

    process = await asyncio.create_subprocess_exec(
        "git",
        "pull",
        "--ff-only",
        cwd=str(project_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"git pull failed: {stderr.decode(errors='replace').strip()}",
        )

    # Rescan after pull
    await service.rescan_project(project_id)

    return {"status": "ok", "output": stdout.decode(errors="replace").strip()}


@router.get("/{project_id}/git", response_model=GitInfoResponse)
async def get_project_git_info(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GitInfoResponse:
    """Get git information for a project."""
    service = ProjectService(session)
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    info = get_git_info(project.path)
    return GitInfoResponse(**info)


@router.post("/{project_id}/parse-config", response_model=ParseConfigResponse)
async def parse_config(
    project_id: int,
    body: ParseConfigRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ParseConfigResponse:
    """Parse a config file from a project and return structured representation."""
    from backend.services.config_parser import parse_config_file

    service = ProjectService(session)
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        result = parse_config_file(project.path, body.config_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Config file not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ParseConfigResponse(**result)


@router.get("/{project_id}/configs/{config_path:path}", response_model=ConfigContentResponse)
async def get_config_content(
    project_id: int,
    config_path: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConfigContentResponse:
    """Read the contents of a config file within a project."""
    service = ProjectService(session)
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = read_config_file(project.path, config_path)
    if content is None:
        raise HTTPException(status_code=404, detail="Config file not found")

    # Determine format from extension
    fmt = "text"
    if config_path.endswith((".yaml", ".yml")):
        fmt = "yaml"
    elif config_path.endswith(".json"):
        fmt = "json"
    elif config_path.endswith(".toml"):
        fmt = "toml"

    return ConfigContentResponse(path=config_path, content=content, format=fmt)
