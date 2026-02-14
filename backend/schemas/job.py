"""Job schemas for API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas import JobStatus, JobType


class EvalJobRequest(BaseModel):
    """Request to start an evaluation job."""

    run_id: int
    checkpoint: str = Field(
        default="best",
        description="Checkpoint selection: 'best', 'latest', or epoch number",
    )
    bit_lengths: list[int] = Field(
        default=[8, 16, 32, 64, 128],
        description="Bit lengths to evaluate",
    )
    k_values: list[int] = Field(
        default=[1, 5, 10],
        description="K values for P@K metrics",
    )


class IndexBuildJobRequest(BaseModel):
    """Request to start an index build job."""

    run_id: int
    checkpoint: str = Field(
        default="best",
        description="Checkpoint selection: 'best', 'latest', or epoch number",
    )
    image_dir: str | None = Field(
        default=None,
        description="Directory containing images to index",
    )
    captions_file: str | None = Field(
        default=None,
        description="JSON file with captions list",
    )
    thumbnail_size: int = Field(default=64)
    batch_size: int = Field(default=32)


class JobResponse(BaseModel):
    """Response schema for a job."""

    id: int
    job_type: JobType
    run_id: int
    status: JobStatus
    progress: int
    config_json: dict[str, Any]
    result_json: dict[str, Any]
    error_message: str | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class JobProgressUpdate(BaseModel):
    """Internal progress update from a running job."""

    job_id: int
    progress: int = Field(ge=0, le=100)
    status: JobStatus | None = None
    result_json: dict[str, Any] | None = None
    error_message: str | None = None
