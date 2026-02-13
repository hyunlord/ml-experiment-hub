"""Business logic for experiment management."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from backend.core.engine import engine
from backend.models.experiment import Experiment
from backend.schemas.experiment import ExperimentCreate, ExperimentUpdate
from shared.schemas import ExperimentStatus


class ExperimentService:
    """Service for managing experiments."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize experiment service."""
        self.session = session

    async def list_experiments(
        self,
        skip: int = 0,
        limit: int = 100,
        status: ExperimentStatus | None = None,
    ) -> list[Experiment]:
        """List experiments with pagination and optional status filter."""
        query = select(Experiment)
        if status is not None:
            query = query.where(Experiment.status == status)
        query = query.offset(skip).limit(limit).order_by(Experiment.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_experiments(self, status: ExperimentStatus | None = None) -> int:
        """Count total experiments with optional status filter."""
        query = select(func.count()).select_from(Experiment)
        if status is not None:
            query = query.where(Experiment.status == status)
        result = await self.session.execute(query)
        count = result.scalar()
        return count if count is not None else 0

    async def create_experiment(self, experiment: ExperimentCreate) -> Experiment:
        """Create a new experiment."""
        db_experiment = Experiment(
            name=experiment.name,
            description=experiment.description,
            framework=experiment.framework,
            script_path=experiment.script_path,
            hyperparameters=experiment.hyperparameters,
            tags=experiment.tags,
            status=ExperimentStatus.PENDING,
        )
        self.session.add(db_experiment)
        await self.session.commit()
        await self.session.refresh(db_experiment)
        return db_experiment

    async def get_experiment(self, experiment_id: int) -> Experiment | None:
        """Get experiment by ID."""
        result = await self.session.execute(
            select(Experiment).where(Experiment.id == experiment_id)
        )
        return result.scalar_one_or_none()

    async def update_experiment(
        self, experiment_id: int, updates: ExperimentUpdate
    ) -> Experiment | None:
        """Update experiment details."""
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
        """Delete an experiment."""
        experiment = await self.get_experiment(experiment_id)
        if not experiment:
            return False

        # Stop if running
        if experiment.status == ExperimentStatus.RUNNING:
            await engine.stop_experiment(experiment_id)

        await self.session.delete(experiment)
        await self.session.commit()
        return True

    async def start_experiment(self, experiment_id: int) -> Experiment | None:
        """Start an experiment."""
        experiment = await self.get_experiment(experiment_id)
        if not experiment:
            return None

        # Validate status
        if experiment.status == ExperimentStatus.RUNNING:
            raise ValueError("Experiment is already running")

        # Update status
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.utcnow()
        experiment.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(experiment)

        # Start execution
        await engine.start_experiment(
            experiment_id,
            experiment.script_path,
            experiment.hyperparameters,
            self.session,
        )

        return experiment

    async def stop_experiment(self, experiment_id: int) -> Experiment | None:
        """Stop a running experiment."""
        experiment = await self.get_experiment(experiment_id)
        if not experiment:
            return None

        # Validate status
        if experiment.status != ExperimentStatus.RUNNING:
            raise ValueError("Experiment is not running")

        # Stop execution
        stopped = await engine.stop_experiment(experiment_id)
        if not stopped:
            raise ValueError("Failed to stop experiment process")

        # Update status
        experiment.status = ExperimentStatus.CANCELLED
        experiment.completed_at = datetime.utcnow()
        experiment.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(experiment)

        return experiment
