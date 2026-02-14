"""REST API endpoints for experiment queue management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.models.database import get_session
from backend.models.experiment import ExperimentConfig, QueueEntry
from shared.schemas import QueueStatus

router = APIRouter(prefix="/api/queue", tags=["queue"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class QueueEntryResponse(BaseModel):
    """Queue entry response."""

    id: int
    experiment_config_id: int
    experiment_name: str = ""
    position: int
    status: QueueStatus
    run_id: int | None = None
    error_message: str | None = None
    added_at: str
    started_at: str | None = None
    completed_at: str | None = None

    model_config = {"from_attributes": True}


class AddToQueueRequest(BaseModel):
    """Add experiment to queue."""

    experiment_config_id: int


class ReorderRequest(BaseModel):
    """Reorder queue entries."""

    entry_ids: list[int] = Field(description="Entry IDs in desired order")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_response(entry: QueueEntry, session: AsyncSession) -> QueueEntryResponse:
    """Build response with experiment name."""
    result = await session.execute(
        select(ExperimentConfig).where(ExperimentConfig.id == entry.experiment_config_id)
    )
    exp = result.scalar_one_or_none()
    return QueueEntryResponse(
        id=entry.id,  # type: ignore[arg-type]
        experiment_config_id=entry.experiment_config_id,
        experiment_name=exp.name if exp else f"Experiment #{entry.experiment_config_id}",
        position=entry.position,
        status=entry.status,
        run_id=entry.run_id,
        error_message=entry.error_message,
        added_at=entry.added_at.isoformat(),
        started_at=entry.started_at.isoformat() if entry.started_at else None,
        completed_at=entry.completed_at.isoformat() if entry.completed_at else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[QueueEntryResponse])
async def list_queue(
    session: Annotated[AsyncSession, Depends(get_session)],
    include_completed: bool = False,
) -> list[QueueEntryResponse]:
    """List queue entries, ordered by position."""
    query = select(QueueEntry)
    if not include_completed:
        query = query.where(
            QueueEntry.status.in_([QueueStatus.WAITING, QueueStatus.RUNNING])  # type: ignore[union-attr]
        )
    query = query.order_by(QueueEntry.position)
    result = await session.execute(query)
    entries = list(result.scalars().all())
    return [await _build_response(e, session) for e in entries]


@router.post("", response_model=QueueEntryResponse, status_code=201)
async def add_to_queue(
    body: AddToQueueRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> QueueEntryResponse:
    """Add an experiment to the queue."""
    # Verify experiment exists
    result = await session.execute(
        select(ExperimentConfig).where(ExperimentConfig.id == body.experiment_config_id)
    )
    exp = result.scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Check if already in queue (waiting/running)
    result = await session.execute(
        select(QueueEntry).where(
            QueueEntry.experiment_config_id == body.experiment_config_id,
            QueueEntry.status.in_([QueueStatus.WAITING, QueueStatus.RUNNING]),  # type: ignore[union-attr]
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Experiment already in queue")

    # Get next position
    result = await session.execute(
        select(QueueEntry)
        .where(QueueEntry.status.in_([QueueStatus.WAITING, QueueStatus.RUNNING]))  # type: ignore[union-attr]
        .order_by(QueueEntry.position.desc())  # type: ignore[union-attr]
        .limit(1)
    )
    last = result.scalar_one_or_none()
    next_position = (last.position + 1) if last else 0

    entry = QueueEntry(
        experiment_config_id=body.experiment_config_id,
        position=next_position,
        status=QueueStatus.WAITING,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    return await _build_response(entry, session)


@router.delete("/{entry_id}")
async def remove_from_queue(
    entry_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Remove an entry from the queue."""
    result = await session.execute(select(QueueEntry).where(QueueEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    if entry.status == QueueStatus.RUNNING:
        raise HTTPException(
            status_code=400, detail="Cannot remove running entry. Stop the run first."
        )

    await session.delete(entry)
    await session.commit()
    return {"status": "removed"}


@router.post("/reorder")
async def reorder_queue(
    body: ReorderRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Reorder queue entries by providing entry IDs in desired order."""
    for position, entry_id in enumerate(body.entry_ids):
        result = await session.execute(select(QueueEntry).where(QueueEntry.id == entry_id))
        entry = result.scalar_one_or_none()
        if entry and entry.status == QueueStatus.WAITING:
            entry.position = position
    await session.commit()
    return {"status": "reordered"}


@router.get("/history", response_model=list[QueueEntryResponse])
async def queue_history(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 20,
) -> list[QueueEntryResponse]:
    """Get completed/failed queue entries (history)."""
    result = await session.execute(
        select(QueueEntry)
        .where(
            QueueEntry.status.in_(  # type: ignore[union-attr]
                [QueueStatus.COMPLETED, QueueStatus.FAILED, QueueStatus.CANCELLED]
            )
        )
        .order_by(QueueEntry.completed_at.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    entries = list(result.scalars().all())
    return [await _build_response(e, session) for e in entries]
