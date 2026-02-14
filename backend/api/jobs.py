"""REST API endpoints for background job management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_session
from backend.schemas.job import (
    EvalJobRequest,
    IndexBuildJobRequest,
    JobProgressUpdate,
    JobResponse,
)
from backend.services.job_manager import job_manager
from shared.schemas import JobType

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/eval", response_model=JobResponse, status_code=201)
async def create_eval_job(
    body: EvalJobRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobResponse:
    """Start an evaluation job for a run."""
    try:
        job = await job_manager.create_eval_job(
            run_id=body.run_id,
            config={
                "checkpoint": body.checkpoint,
                "bit_lengths": body.bit_lengths,
                "k_values": body.k_values,
            },
            session=session,
        )
        return JobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/index-build", response_model=JobResponse, status_code=201)
async def create_index_build_job(
    body: IndexBuildJobRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobResponse:
    """Start an index build job for a run."""
    try:
        job = await job_manager.create_index_build_job(
            run_id=body.run_id,
            config={
                "checkpoint": body.checkpoint,
                "image_dir": body.image_dir,
                "captions_file": body.captions_file,
                "thumbnail_size": body.thumbnail_size,
                "batch_size": body.batch_size,
            },
            session=session,
        )
        return JobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobResponse:
    """Get job details and current progress."""
    job = await job_manager.get_job(job_id, session)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    session: Annotated[AsyncSession, Depends(get_session)],
    job_type: JobType | None = Query(default=None),
    run_id: int | None = Query(default=None),
) -> list[JobResponse]:
    """List jobs with optional filters."""
    jobs = await job_manager.list_jobs(session=session, job_type=job_type, run_id=run_id)
    return [JobResponse.model_validate(j) for j in jobs]


@router.post("/{job_id}/progress", response_model=JobResponse)
async def update_job_progress(
    job_id: int,
    body: JobProgressUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobResponse:
    """Internal endpoint: update job progress from subprocess."""
    job = await job_manager.update_progress(
        job_id=job_id,
        progress=body.progress,
        session=session,
        status=body.status,
        result_json=body.result_json,
        error_message=body.error_message,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Cancel a running job."""
    cancelled = await job_manager.cancel_job(job_id, session)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Job not found or not running")
    return {"status": "cancelled"}
