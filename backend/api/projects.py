"""REST API endpoints for project management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_session
from backend.schemas.project import (
    ConfigContentResponse,
    GitInfoResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    ScanRequest,
    ScanResponse,
)
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
