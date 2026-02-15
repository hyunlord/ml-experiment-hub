"""Business logic for experiment management."""

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from backend.models.experiment import ConfigSchema, ExperimentConfig
from backend.schemas.config_schema import SchemaDefinition
from backend.schemas.experiment import ExperimentCreate, ExperimentUpdate
from shared.schemas import ExperimentConfigStatus
from shared.utils import diff_configs


class ExperimentService:
    """Service for managing experiment configurations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize experiment service."""
        self.session = session

    async def list_experiments(
        self,
        skip: int = 0,
        limit: int = 100,
        status: ExperimentConfigStatus | None = None,
        schema_id: int | None = None,
        tags: list[str] | None = None,
    ) -> list[ExperimentConfig]:
        """List experiment configurations with pagination and filters."""
        query = select(ExperimentConfig)
        if status is not None:
            query = query.where(ExperimentConfig.status == status)
        if schema_id is not None:
            query = query.where(ExperimentConfig.config_schema_id == schema_id)
        if tags:
            # Filter experiments that contain ALL specified tags (AND logic).
            # JSON array containment varies by DB; for SQLite we use Python
            # post-filter. For PostgreSQL this would use @> operator.
            pass  # handled via post-filter below
        query = query.offset(skip).limit(limit).order_by(ExperimentConfig.created_at.desc())
        result = await self.session.execute(query)
        experiments = list(result.scalars().all())

        # Post-filter by tags for SQLite compatibility
        if tags:
            tag_set = set(tags)
            experiments = [exp for exp in experiments if tag_set.issubset(set(exp.tags or []))]

        return experiments

    async def count_experiments(
        self,
        status: ExperimentConfigStatus | None = None,
        schema_id: int | None = None,
    ) -> int:
        """Count total experiment configurations with optional filters."""
        query = select(func.count()).select_from(ExperimentConfig)
        if status is not None:
            query = query.where(ExperimentConfig.status == status)
        if schema_id is not None:
            query = query.where(ExperimentConfig.config_schema_id == schema_id)
        result = await self.session.execute(query)
        count = result.scalar()
        return count if count is not None else 0

    async def create_experiment(self, data: ExperimentCreate) -> ExperimentConfig:
        """Create a new experiment configuration with optional schema validation."""
        # Validate name uniqueness within project scope
        await self._validate_name_unique(name=data.name, project_id=data.project_id)

        # Validate config against schema if schema_id is provided
        if data.schema_id is not None:
            await self._validate_config_against_schema(data.schema_id, data.config)

        db_experiment = ExperimentConfig(
            name=data.name,
            description=data.description,
            config_json=data.config,
            config_schema_id=data.schema_id,
            project_id=data.project_id,
            tags=data.tags,
            status=ExperimentConfigStatus.DRAFT,
        )
        self.session.add(db_experiment)
        await self.session.commit()
        await self.session.refresh(db_experiment)
        return db_experiment

    async def get_experiment(self, experiment_id: int) -> ExperimentConfig | None:
        """Get experiment configuration by ID."""
        result = await self.session.execute(
            select(ExperimentConfig).where(ExperimentConfig.id == experiment_id)
        )
        return result.scalar_one_or_none()

    async def update_experiment(
        self, experiment_id: int, updates: ExperimentUpdate
    ) -> ExperimentConfig | None:
        """Update experiment configuration (draft status only)."""
        experiment = await self.get_experiment(experiment_id)
        if not experiment:
            return None

        if experiment.status != ExperimentConfigStatus.DRAFT:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot update experiment in '{experiment.status.value}' status. Only DRAFT experiments can be modified.",
            )

        update_data = updates.model_dump(exclude_unset=True)

        # Validate name uniqueness if name is being changed
        if "name" in update_data and update_data["name"] != experiment.name:
            await self._validate_name_unique(
                name=update_data["name"],
                project_id=experiment.project_id,
                exclude_id=experiment_id,
            )

        # Map API field names to DB field names
        if "config" in update_data:
            # Validate against schema if experiment has one
            if experiment.config_schema_id is not None and update_data["config"] is not None:
                await self._validate_config_against_schema(
                    experiment.config_schema_id, update_data["config"]
                )
            update_data["config_json"] = update_data.pop("config")

        for key, value in update_data.items():
            setattr(experiment, key, value)

        experiment.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(experiment)
        return experiment

    async def delete_experiment(self, experiment_id: int) -> bool:
        """Delete an experiment configuration."""
        experiment = await self.get_experiment(experiment_id)
        if not experiment:
            return False

        await self.session.delete(experiment)
        await self.session.commit()
        return True

    async def clone_experiment(self, experiment_id: int) -> ExperimentConfig | None:
        """Clone an experiment with '(copy)' suffix on the name."""
        source = await self.get_experiment(experiment_id)
        if not source:
            return None

        clone = ExperimentConfig(
            name=f"{source.name} (copy)",
            description=source.description,
            config_json=dict(source.config_json) if source.config_json else {},
            config_schema_id=source.config_schema_id,
            tags=list(source.tags) if source.tags else [],
            status=ExperimentConfigStatus.DRAFT,
        )
        self.session.add(clone)
        await self.session.commit()
        await self.session.refresh(clone)
        return clone

    async def diff_experiments(self, experiment_id: int, compare_with_id: int) -> dict[str, Any]:
        """Compare config of two experiments and return differences."""
        base = await self.get_experiment(experiment_id)
        if not base:
            raise HTTPException(status_code=404, detail="Experiment not found")

        other = await self.get_experiment(compare_with_id)
        if not other:
            raise HTTPException(
                status_code=404,
                detail=f"Comparison experiment {compare_with_id} not found",
            )

        return diff_configs(base.config_json or {}, other.config_json or {})

    async def check_name_available(
        self,
        name: str,
        project_id: int | None = None,
        exclude_id: int | None = None,
    ) -> tuple[bool, str | None]:
        """Check if an experiment name is available within a project scope.

        Returns (available, suggestion) where suggestion is an alternative name
        if the name is taken.
        """
        import re

        query = select(ExperimentConfig).where(ExperimentConfig.name == name)
        if project_id is not None:
            query = query.where(ExperimentConfig.project_id == project_id)
        if exclude_id is not None:
            query = query.where(ExperimentConfig.id != exclude_id)
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()

        if not existing:
            return True, None

        # Generate suggestion: strip trailing _NNN or _copy_N, then increment
        base = re.sub(r"(_copy)?(_\d+)?$", "", name)
        for i in range(2, 100):
            candidate = f"{base}_{i:03d}"
            q = select(ExperimentConfig).where(ExperimentConfig.name == candidate)
            if project_id is not None:
                q = q.where(ExperimentConfig.project_id == project_id)
            r = await self.session.execute(q)
            if not r.scalar_one_or_none():
                return False, candidate

        return False, f"{base}_new"

    async def _validate_name_unique(
        self,
        name: str,
        project_id: int | None = None,
        exclude_id: int | None = None,
    ) -> None:
        """Raise 409 if experiment name already exists in the project scope."""
        available, suggestion = await self.check_name_available(
            name=name,
            project_id=project_id,
            exclude_id=exclude_id,
        )
        if not available:
            detail = f"Experiment name '{name}' already exists"
            if suggestion:
                detail += f". Suggestion: '{suggestion}'"
            raise HTTPException(status_code=409, detail=detail)

    async def _validate_config_against_schema(self, schema_id: int, config: dict[str, Any]) -> None:
        """Validate config keys against a ConfigSchema's required fields."""
        result = await self.session.execute(
            select(ConfigSchema).where(ConfigSchema.id == schema_id)
        )
        schema = result.scalar_one_or_none()
        if not schema:
            raise HTTPException(status_code=404, detail=f"Schema {schema_id} not found")

        # Parse the stored schema definition
        try:
            definition = SchemaDefinition.model_validate(schema.fields_schema)
        except Exception:
            # Schema is stored but not parseable — skip validation
            return

        # Check required fields are present in config
        missing = []
        for field in definition.fields:
            if field.required and field.key not in config:
                missing.append(field.key)

        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Missing required config fields: {', '.join(missing)}",
            )
