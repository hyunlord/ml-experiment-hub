"""Business logic for experiment management."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from backend.models.experiment import ExperimentConfig
from backend.schemas.experiment import ExperimentCreate, ExperimentUpdate
from shared.schemas import ExperimentConfigStatus


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
    ) -> list[ExperimentConfig]:
        """List experiment configurations with pagination and optional status filter."""
        query = select(ExperimentConfig)
        if status is not None:
            query = query.where(ExperimentConfig.status == status)
        query = query.offset(skip).limit(limit).order_by(ExperimentConfig.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_experiments(self, status: ExperimentConfigStatus | None = None) -> int:
        """Count total experiment configurations with optional status filter."""
        query = select(func.count()).select_from(ExperimentConfig)
        if status is not None:
            query = query.where(ExperimentConfig.status == status)
        result = await self.session.execute(query)
        count = result.scalar()
        return count if count is not None else 0

    async def create_experiment(self, experiment: ExperimentCreate) -> ExperimentConfig:
        """Create a new experiment configuration."""
        db_experiment = ExperimentConfig(
            name=experiment.name,
            description=experiment.description,
            config_json=experiment.config_json,
            config_schema_id=experiment.config_schema_id,
            tags=experiment.tags,
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
        """Update experiment configuration details."""
        experiment = await self.get_experiment(experiment_id)
        if not experiment:
            return None

        update_data = updates.model_dump(exclude_unset=True)
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
