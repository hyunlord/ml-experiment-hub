"""Dataset management API.

Provides endpoints for:
- Listing datasets with file-system status (ready/raw_only/not_found/preparing)
- CRUD: register, update, delete datasets
- Auto-detect: infer format/type from path
- Split configuration and preview
- JSONL preview (random samples with language detection)
- Triggering JSONL prepare jobs
- Serving dataset images for preview thumbnails
- Legacy /status endpoint for backward compatibility
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.config import settings
from backend.models.database import get_session
from backend.models.experiment import DatasetDefinition, ExperimentRun, Job
from backend.services.dataset_registry import (
    check_prepare_job_status,
    compute_split_preview,
    compute_status,
    detect_dataset,
    get_file_stats,
    language_stats,
    preview_jsonl,
    seed_datasets,
)
from shared.schemas import (
    DatasetFormat,
    DatasetStatus,
    DatasetType,
    JobStatus,
    JobType,
    SplitMethod,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------


class DatasetResponse(BaseModel):
    """Dataset list/detail response."""

    id: int
    key: str
    name: str
    description: str
    dataset_type: str
    dataset_format: str
    data_root: str
    jsonl_path: str
    raw_path: str
    raw_format: str
    split_method: str
    splits_config: dict[str, Any]
    status: DatasetStatus
    entry_count: int | None = None
    size_bytes: int | None = None
    is_seed: bool = False
    prepare_job_id: int | None = None
    prepare_progress: int | None = None

    model_config = {"from_attributes": True}


class CreateDatasetRequest(BaseModel):
    """Request to register a new dataset."""

    name: str
    key: str | None = None
    description: str = ""
    dataset_type: str = DatasetType.IMAGE_TEXT.value
    dataset_format: str = DatasetFormat.JSONL.value
    data_root: str = ""
    raw_path: str = ""
    jsonl_path: str = ""
    raw_format: str = "custom"
    split_method: str = SplitMethod.NONE.value
    splits_config: dict[str, Any] = {}


class UpdateDatasetRequest(BaseModel):
    """Request to update a dataset."""

    name: str | None = None
    description: str | None = None
    dataset_type: str | None = None
    dataset_format: str | None = None
    data_root: str | None = None
    raw_path: str | None = None
    jsonl_path: str | None = None
    raw_format: str | None = None
    split_method: str | None = None
    splits_config: dict[str, Any] | None = None


class DetectRequest(BaseModel):
    """Request to auto-detect dataset properties."""

    path: str


class DetectResponse(BaseModel):
    """Auto-detect result."""

    exists: bool
    format: str | None = None
    type: str | None = None
    entry_count: int | None = None
    raw_format: str | None = None
    error: str | None = None


class SplitUpdateRequest(BaseModel):
    """Request to update split configuration."""

    split_method: str
    splits_config: dict[str, Any] = {}


class SplitPreviewResponse(BaseModel):
    """Split preview with per-split counts."""

    dataset_id: int
    split_method: str
    splits: dict[str, int]


class PreviewResponse(BaseModel):
    """Dataset JSONL preview response."""

    dataset_id: int
    dataset_name: str
    dataset_type: str
    samples: list[dict[str, Any]]
    language_stats: dict[str, int]
    total_entries: int | None = None


class PrepareResponse(BaseModel):
    """Prepare job creation response."""

    job_id: int
    dataset_id: int
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Generate a URL-safe key from a name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug or "dataset"


async def _build_dataset_response(
    ds: DatasetDefinition,
    session: AsyncSession,
) -> DatasetResponse:
    """Build a DatasetResponse with computed status and optional job progress."""
    status = await check_prepare_job_status(ds, session)

    # If status just changed from PREPARING, re-compute
    if status != DatasetStatus.PREPARING and ds.prepare_job_id is not None:
        status = compute_status(ds)

    # Get progress if preparing
    progress = None
    if status == DatasetStatus.PREPARING and ds.prepare_job_id is not None:
        result = await session.execute(select(Job).where(Job.id == ds.prepare_job_id))
        job = result.scalar_one_or_none()
        if job:
            progress = job.progress

    return DatasetResponse(
        id=ds.id,  # type: ignore[arg-type]
        key=ds.key,
        name=ds.name,
        description=ds.description,
        dataset_type=ds.dataset_type.value
        if hasattr(ds.dataset_type, "value")
        else ds.dataset_type,
        dataset_format=ds.dataset_format.value
        if hasattr(ds.dataset_format, "value")
        else ds.dataset_format,
        data_root=ds.data_root,
        jsonl_path=ds.jsonl_path,
        raw_path=ds.raw_path,
        raw_format=ds.raw_format,
        split_method=ds.split_method.value
        if hasattr(ds.split_method, "value")
        else ds.split_method,
        splits_config=ds.splits_config or {},
        status=status,
        entry_count=ds.entry_count,
        size_bytes=ds.size_bytes,
        is_seed=ds.is_seed,
        prepare_job_id=ds.prepare_job_id,
        prepare_progress=progress,
    )


# ---------------------------------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DatasetResponse]:
    """List all registered datasets with current status."""
    # Ensure seed data exists
    await seed_datasets(session)

    result = await session.execute(select(DatasetDefinition).order_by(DatasetDefinition.key))
    datasets = list(result.scalars().all())

    responses = []
    for ds in datasets:
        resp = await _build_dataset_response(ds, session)
        responses.append(resp)

    return responses


@router.post("", response_model=DatasetResponse, status_code=201)
async def create_dataset(
    body: CreateDatasetRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetResponse:
    """Register a new dataset."""
    key = body.key or _slugify(body.name)

    # Check for duplicate key
    result = await session.execute(select(DatasetDefinition).where(DatasetDefinition.key == key))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Dataset key '{key}' already exists")

    ds = DatasetDefinition(
        key=key,
        name=body.name,
        description=body.description,
        dataset_type=DatasetType(body.dataset_type),
        dataset_format=DatasetFormat(body.dataset_format),
        data_root=body.data_root,
        raw_path=body.raw_path,
        jsonl_path=body.jsonl_path,
        raw_format=body.raw_format,
        split_method=SplitMethod(body.split_method),
        splits_config=body.splits_config,
        is_seed=False,
    )

    # Auto-compute stats if JSONL already exists
    status = compute_status(ds)
    if status == DatasetStatus.READY:
        stats = get_file_stats(ds)
        ds.entry_count = stats["entry_count"]
        ds.size_bytes = stats["size_bytes"]

    session.add(ds)
    await session.commit()
    await session.refresh(ds)

    return await _build_dataset_response(ds, session)


@router.get("/status")
async def dataset_status_legacy(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, dict[str, Any]]:
    """Legacy status endpoint for backward compatibility.

    Returns dict mapping dataset key to {available, entries, expected_path, label}.
    """
    await seed_datasets(session)

    result = await session.execute(select(DatasetDefinition))
    datasets = list(result.scalars().all())

    output: dict[str, dict[str, Any]] = {}
    for ds in datasets:
        status = compute_status(ds)
        stats = get_file_stats(ds)
        output[ds.key] = {
            "available": status == DatasetStatus.READY,
            "entries": stats["entry_count"],
            "expected_path": ds.jsonl_path,
            "label": ds.name,
            "status": status.value,
        }

    return output


@router.post("/detect", response_model=DetectResponse)
async def detect_dataset_endpoint(
    body: DetectRequest,
) -> DetectResponse:
    """Auto-detect format, type, and entry count from a path."""
    result = detect_dataset(body.path)
    return DetectResponse(**result)


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetResponse:
    """Get a single dataset by ID."""
    result = await session.execute(
        select(DatasetDefinition).where(DatasetDefinition.id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return await _build_dataset_response(ds, session)


@router.put("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: int,
    body: UpdateDatasetRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetResponse:
    """Update a dataset's metadata."""
    result = await session.execute(
        select(DatasetDefinition).where(DatasetDefinition.id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if body.name is not None:
        ds.name = body.name
    if body.description is not None:
        ds.description = body.description
    if body.dataset_type is not None:
        ds.dataset_type = DatasetType(body.dataset_type)
    if body.dataset_format is not None:
        ds.dataset_format = DatasetFormat(body.dataset_format)
    if body.data_root is not None:
        ds.data_root = body.data_root
    if body.raw_path is not None:
        ds.raw_path = body.raw_path
    if body.jsonl_path is not None:
        ds.jsonl_path = body.jsonl_path
    if body.raw_format is not None:
        ds.raw_format = body.raw_format
    if body.split_method is not None:
        ds.split_method = SplitMethod(body.split_method)
    if body.splits_config is not None:
        ds.splits_config = body.splits_config

    ds.updated_at = datetime.utcnow()

    # Recompute stats if path changed
    status = compute_status(ds)
    if status == DatasetStatus.READY:
        stats = get_file_stats(ds)
        ds.entry_count = stats["entry_count"]
        ds.size_bytes = stats["size_bytes"]

    await session.commit()
    await session.refresh(ds)

    return await _build_dataset_response(ds, session)


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete a dataset registration (does not delete files)."""
    result = await session.execute(
        select(DatasetDefinition).where(DatasetDefinition.id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    await session.delete(ds)
    await session.commit()


# ---------------------------------------------------------------------------
# Split endpoints
# ---------------------------------------------------------------------------


@router.put("/{dataset_id}/splits", response_model=DatasetResponse)
async def update_splits(
    dataset_id: int,
    body: SplitUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetResponse:
    """Update split configuration for a dataset."""
    result = await session.execute(
        select(DatasetDefinition).where(DatasetDefinition.id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    ds.split_method = SplitMethod(body.split_method)
    ds.splits_config = body.splits_config
    ds.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(ds)

    return await _build_dataset_response(ds, session)


@router.get("/{dataset_id}/splits/preview", response_model=SplitPreviewResponse)
async def preview_splits(
    dataset_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    split_method: str | None = Query(default=None),
) -> SplitPreviewResponse:
    """Preview how many entries each split would contain."""
    result = await session.execute(
        select(DatasetDefinition).where(DatasetDefinition.id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    splits = compute_split_preview(ds, split_method=split_method)

    return SplitPreviewResponse(
        dataset_id=ds.id,  # type: ignore[arg-type]
        split_method=split_method
        or (ds.split_method.value if hasattr(ds.split_method, "value") else ds.split_method),
        splits=splits,
    )


# ---------------------------------------------------------------------------
# Preview & Image
# ---------------------------------------------------------------------------


@router.get("/{dataset_id}/preview", response_model=PreviewResponse)
async def preview_dataset(
    dataset_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    n: int = Query(default=5, ge=1, le=20),
) -> PreviewResponse:
    """Preview random samples from a dataset's JSONL file."""
    result = await session.execute(
        select(DatasetDefinition).where(DatasetDefinition.id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    status = compute_status(ds)
    if status != DatasetStatus.READY:
        raise HTTPException(status_code=400, detail="Dataset JSONL not ready for preview")

    samples = preview_jsonl(ds, n=n)
    lang = language_stats(ds)

    ds_type = ds.dataset_type.value if hasattr(ds.dataset_type, "value") else ds.dataset_type

    return PreviewResponse(
        dataset_id=ds.id,  # type: ignore[arg-type]
        dataset_name=ds.name,
        dataset_type=ds_type,
        samples=samples,
        language_stats=lang,
        total_entries=ds.entry_count,
    )


@router.get("/{dataset_id}/image")
async def serve_dataset_image(
    dataset_id: int,
    path: str = Query(description="Relative image path within data_root"),
    session: Annotated[AsyncSession, Depends(get_session)] = None,  # type: ignore[assignment]
) -> FileResponse:
    """Serve a dataset image file for preview thumbnails."""
    result = await session.execute(
        select(DatasetDefinition).where(DatasetDefinition.id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Security: prevent path traversal
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid image path")

    base = Path(settings.DATA_DIR)
    img_path = base / ds.data_root / path if ds.data_root else base / path

    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(str(img_path))


# ---------------------------------------------------------------------------
# Prepare
# ---------------------------------------------------------------------------


@router.post("/{dataset_id}/prepare", response_model=PrepareResponse)
async def prepare_dataset(
    dataset_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PrepareResponse:
    """Trigger JSONL preparation for a raw-only dataset.

    Launches a background prepare worker subprocess.
    """
    result = await session.execute(
        select(DatasetDefinition).where(DatasetDefinition.id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    status = compute_status(ds)
    if status == DatasetStatus.READY:
        raise HTTPException(status_code=400, detail="Dataset JSONL already exists")
    if status == DatasetStatus.PREPARING:
        raise HTTPException(status_code=400, detail="Prepare job already running")
    if status == DatasetStatus.NOT_FOUND:
        raise HTTPException(
            status_code=400,
            detail="Raw data not found. Upload or link data first.",
        )

    # Create a dummy run for the job (jobs require a run_id)
    dummy_run = ExperimentRun(
        experiment_config_id=1,  # placeholder — won't be used
        status="completed",
        log_path="",
        started_at=datetime.utcnow(),
    )
    session.add(dummy_run)
    await session.flush()

    job = Job(
        job_type=JobType.DATASET_PREPARE,
        run_id=dummy_run.id,
        status=JobStatus.PENDING,
        config_json={
            "dataset_id": dataset_id,
            "data_dir": settings.DATA_DIR,
            "data_root": ds.data_root,
            "raw_path": ds.raw_path,
            "jsonl_path": ds.jsonl_path,
            "raw_format": ds.raw_format,
        },
    )
    session.add(job)
    await session.flush()

    # Link job to dataset
    ds.prepare_job_id = job.id
    ds.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(job)

    # Launch subprocess
    job_id = job.id
    assert job_id is not None

    config_data = {
        "job_id": job_id,
        "dataset_id": dataset_id,
        "data_dir": settings.DATA_DIR,
        "data_root": ds.data_root,
        "raw_path": ds.raw_path,
        "jsonl_path": ds.jsonl_path,
        "raw_format": ds.raw_format,
        "server_url": "http://localhost:8002",
    }

    config_fd, config_path = tempfile.mkstemp(prefix=f"prepare_{job_id}_", suffix=".json")
    with os.fdopen(config_fd, "w") as f:
        json.dump(config_data, f)

    cmd = [
        sys.executable,
        "-m",
        "backend.workers.prepare_worker",
        "--config",
        config_path,
    ]

    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"prepare_{job_id}.log"

    try:
        log_file = open(log_path, "w")  # noqa: SIM115
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
        )

        job.status = JobStatus.RUNNING
        job.pid = process.pid
        job.started_at = datetime.utcnow()
        await session.commit()

        # Monitor in background
        asyncio.create_task(_monitor_prepare(job_id, dataset_id, process, log_file, config_path))

    except Exception as e:
        log_file.close()
        os.unlink(config_path)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.ended_at = datetime.utcnow()
        ds.prepare_job_id = None
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Failed to launch prepare job: {e}")

    return PrepareResponse(
        job_id=job_id,
        dataset_id=dataset_id,
        message=f"Prepare job started for {ds.name}",
    )


async def _monitor_prepare(
    job_id: int,
    dataset_id: int,
    process: asyncio.subprocess.Process,
    log_file: Any,
    config_path: str,
) -> None:
    """Monitor prepare subprocess and update job/dataset on completion."""
    from backend.models.database import async_session_maker

    try:
        return_code = await process.wait()

        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()

            if job and job.status == JobStatus.RUNNING:
                if return_code == 0:
                    job.status = JobStatus.COMPLETED
                    job.progress = 100
                else:
                    job.status = JobStatus.FAILED
                    job.error_message = f"Process exited with code {return_code}"
                job.ended_at = datetime.utcnow()

            # Update dataset
            result = await session.execute(
                select(DatasetDefinition).where(DatasetDefinition.id == dataset_id)
            )
            ds = result.scalar_one_or_none()
            if ds:
                ds.prepare_job_id = None
                if job and job.status == JobStatus.COMPLETED:
                    stats = get_file_stats(ds)
                    ds.entry_count = stats["entry_count"]
                    ds.size_bytes = stats["size_bytes"]
                ds.updated_at = datetime.utcnow()

            await session.commit()

        logger.info("Prepare job %d finished with code %d", job_id, return_code)

    except Exception:
        logger.exception("Error monitoring prepare job %d", job_id)
    finally:
        log_file.close()
        try:
            os.unlink(config_path)
        except OSError:
            pass
