"""REST API endpoints for project templates."""

from fastapi import APIRouter, HTTPException, Query

from backend.schemas.project import TemplateConfigSchema, TemplateInfo
from backend.services.template_registry import (
    get_template,
    get_template_config_schema,
    list_templates,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=list[TemplateInfo])
async def get_templates() -> list[TemplateInfo]:
    """List all available project templates."""
    return list_templates()


@router.get("/{template_id}", response_model=TemplateInfo)
async def get_template_detail(template_id: str) -> TemplateInfo:
    """Get template details by ID."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("/{template_id}/schema", response_model=TemplateConfigSchema)
async def get_template_schema(
    template_id: str,
    task: str | None = Query(default=None, description="Task ID to include task-specific fields"),
) -> TemplateConfigSchema:
    """Get the config schema for a template."""
    schema = get_template_config_schema(template_id, task_id=task)
    if not schema:
        raise HTTPException(status_code=404, detail="Template schema not found")
    return schema
