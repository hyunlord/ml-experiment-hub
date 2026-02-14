"""CRUD API endpoints for ConfigSchema management."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from backend.models.database import get_session
from backend.models.experiment import ConfigSchema
from backend.schemas.config_schema import (
    ConfigSchemaCreate,
    ConfigSchemaListResponse,
    ConfigSchemaResponse,
    ConfigSchemaUpdate,
)

router = APIRouter(prefix="/api/schemas", tags=["schemas"])


@router.post("", response_model=ConfigSchemaResponse, status_code=201)
async def create_schema(
    data: ConfigSchemaCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConfigSchemaResponse:
    """Create a new config schema template."""
    schema = ConfigSchema(
        name=data.name,
        description=data.description,
        fields_schema=data.fields_schema.model_dump(),
    )
    session.add(schema)
    await session.commit()
    await session.refresh(schema)
    return ConfigSchemaResponse.model_validate(schema)


@router.get("", response_model=ConfigSchemaListResponse)
async def list_schemas(
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> ConfigSchemaListResponse:
    """List all config schema templates."""
    result = await session.execute(
        select(ConfigSchema).offset(skip).limit(limit).order_by(ConfigSchema.created_at.desc())
    )
    schemas = result.scalars().all()

    count_result = await session.execute(select(func.count()).select_from(ConfigSchema))
    total = count_result.scalar() or 0

    return ConfigSchemaListResponse(
        schemas=[ConfigSchemaResponse.model_validate(s) for s in schemas],
        total=total,
    )


@router.get("/{schema_id}", response_model=ConfigSchemaResponse)
async def get_schema(
    schema_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConfigSchemaResponse:
    """Get a config schema by ID."""
    result = await session.execute(select(ConfigSchema).where(ConfigSchema.id == schema_id))
    schema = result.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    return ConfigSchemaResponse.model_validate(schema)


@router.put("/{schema_id}", response_model=ConfigSchemaResponse)
async def update_schema(
    schema_id: int,
    data: ConfigSchemaUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConfigSchemaResponse:
    """Update a config schema."""
    result = await session.execute(select(ConfigSchema).where(ConfigSchema.id == schema_id))
    schema = result.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    update_data = data.model_dump(exclude_unset=True)
    if "fields_schema" in update_data and update_data["fields_schema"] is not None:
        update_data["fields_schema"] = data.fields_schema.model_dump()

    for key, value in update_data.items():
        setattr(schema, key, value)

    schema.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(schema)
    return ConfigSchemaResponse.model_validate(schema)


@router.delete("/{schema_id}", status_code=204)
async def delete_schema(
    schema_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete a config schema."""
    result = await session.execute(select(ConfigSchema).where(ConfigSchema.id == schema_id))
    schema = result.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    await session.delete(schema)
    await session.commit()
