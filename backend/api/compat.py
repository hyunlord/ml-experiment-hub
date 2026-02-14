"""Compatibility bridge for vlm_quantization MonitorCallback.

Translates MonitorCallback's endpoint format to ml-experiment-hub's
internal metrics ingestion pipeline. This allows the training script
to post metrics without any code changes.

MonitorCallback endpoints:
    POST /api/training/status   -> status update + WS broadcast
    POST /api/metrics/training  -> POST /api/runs/{run_id}/metrics (training)
    POST /api/metrics/eval      -> POST /api/runs/{run_id}/metrics (validation)
    POST /api/metrics/hash_analysis -> stored as metric with type prefix
    POST /api/checkpoints/register  -> no-op (ack only)
    POST /api/checkpoints/sync      -> no-op (ack only)
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.api.websocket import manager
from backend.models.database import get_session
from backend.models.experiment import ExperimentRun, MetricLog
from shared.schemas import RunStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["compat"])


# ---------------------------------------------------------------------------
# Request schemas (matching MonitorCallback payloads)
# ---------------------------------------------------------------------------


class TrainingStatusPayload(BaseModel):
    """Payload from MonitorCallback.on_train_start / on_train_batch_end / on_fit_end."""

    run_id: str | int
    epoch: int = 0
    step: int = 0
    total_epochs: int = 0
    total_steps: int = 0
    is_training: bool = True
    config: dict[str, Any] | None = None


class TrainingMetricsPayload(BaseModel):
    """Payload from MonitorCallback.on_train_batch_end."""

    run_id: str | int
    step: int
    epoch: int = 0
    # All remaining fields are metrics
    model_config = {"extra": "allow"}


class EvalMetricsPayload(BaseModel):
    """Payload from MonitorCallback.on_validation_epoch_end."""

    run_id: str | int
    epoch: int = 0
    step: int = 0
    model_config = {"extra": "allow"}


class HashAnalysisPayload(BaseModel):
    """Payload from MonitorCallback hash analysis."""

    run_id: str | int
    epoch: int = 0
    step: int = 0
    model_config = {"extra": "allow"}


class CheckpointPayload(BaseModel):
    """Payload from MonitorCallback checkpoint events."""

    run_id: str | int
    epoch: int = 0
    step: int = 0
    path: str = ""
    val_loss: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_run_id(run_id_raw: str | int, session: AsyncSession) -> int:
    """Resolve a run_id (string or int) to the integer DB run ID.

    The MonitorCallback may send:
    - An integer run_id (when hub injects it via adapter)
    - A timestamp string like "20260213_143000"

    We try int conversion first, then fall back to looking up
    the most recent running ExperimentRun.
    """
    # Direct integer
    try:
        return int(run_id_raw)
    except (ValueError, TypeError):
        pass

    # Fallback: find the most recent running ExperimentRun
    result = await session.execute(
        select(ExperimentRun)
        .where(ExperimentRun.status == RunStatus.RUNNING)
        .order_by(ExperimentRun.started_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run:
        logger.info(
            "Resolved string run_id '%s' to ExperimentRun id=%d",
            run_id_raw,
            run.id,
        )
        return run.id  # type: ignore[return-value]

    raise HTTPException(
        status_code=404,
        detail=f"Cannot resolve run_id '{run_id_raw}' to an active run",
    )


def _extract_metrics(payload: BaseModel, exclude: set[str] | None = None) -> dict[str, Any]:
    """Extract metric fields from a pydantic model with extra='allow'.

    Excludes known non-metric fields like run_id, epoch, step, config.
    """
    skip = {
        "run_id",
        "epoch",
        "step",
        "config",
        "is_training",
        "total_epochs",
        "total_steps",
        "path",
        "val_loss",
    }
    if exclude:
        skip |= exclude
    data = payload.model_dump(exclude_none=True)
    return {k: v for k, v in data.items() if k not in skip and v is not None}


async def _ingest(
    run_id: int,
    step: int,
    epoch: int,
    metrics: dict[str, Any],
    session: AsyncSession,
) -> None:
    """Persist metrics and broadcast via WebSocket."""
    if not metrics:
        return

    log_entry = MetricLog(
        run_id=run_id,
        step=step,
        epoch=epoch,
        metrics_json=metrics,
        timestamp=datetime.utcnow(),
    )
    session.add(log_entry)
    await session.commit()

    await manager.broadcast(
        run_id,
        {
            "type": "metric",
            "run_id": run_id,
            "step": step,
            "epoch": epoch,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        },
        channel="metrics",
    )


# ---------------------------------------------------------------------------
# Bridge endpoints
# ---------------------------------------------------------------------------


@router.post("/api/training/status")
async def compat_training_status(
    body: TrainingStatusPayload,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Bridge: MonitorCallback training status updates.

    Broadcasts run status via WebSocket so the dashboard shows
    training progress (epoch, step, total_steps).
    """
    run_id = await _resolve_run_id(body.run_id, session)

    # Broadcast status to metrics channel
    await manager.broadcast(
        run_id,
        {
            "type": "training_status",
            "run_id": run_id,
            "epoch": body.epoch,
            "step": body.step,
            "total_epochs": body.total_epochs,
            "total_steps": body.total_steps,
            "is_training": body.is_training,
        },
        channel="metrics",
    )

    # If training ended, update run status
    if not body.is_training:
        result = await session.execute(select(ExperimentRun).where(ExperimentRun.id == run_id))
        run = result.scalar_one_or_none()
        if run and run.status == RunStatus.RUNNING:
            run.status = RunStatus.COMPLETED
            run.ended_at = datetime.utcnow()
            await session.commit()

    return {"status": "ok"}


@router.post("/api/metrics/training")
async def compat_training_metrics(
    body: TrainingMetricsPayload,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Bridge: MonitorCallback training step metrics.

    Translates named loss fields (loss_total, loss_contrastive, ...)
    into the hub's generic metrics dict format.
    """
    run_id = await _resolve_run_id(body.run_id, session)
    metrics = _extract_metrics(body)
    await _ingest(run_id, body.step, body.epoch, metrics, session)
    return {"status": "ok"}


@router.post("/api/metrics/eval")
async def compat_eval_metrics(
    body: EvalMetricsPayload,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Bridge: MonitorCallback validation epoch metrics.

    Stores eval metrics (mAP, precision@K, val losses, hash quality)
    as a single MetricLog entry.
    """
    run_id = await _resolve_run_id(body.run_id, session)
    metrics = _extract_metrics(body)

    # Prefix eval metrics for easy filtering in the dashboard
    prefixed = {f"eval/{k}" if not k.startswith("val_") else k: v for k, v in metrics.items()}
    await _ingest(run_id, body.step, body.epoch, prefixed, session)
    return {"status": "ok"}


@router.post("/api/metrics/hash_analysis")
async def compat_hash_analysis(
    body: HashAnalysisPayload,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Bridge: MonitorCallback hash analysis data.

    Flattens nested hash analysis (activation rates, entropy, similarity matrix)
    into individual hash/ prefixed metric keys for the dashboard.
    Non-scalar data (thumbnails, sample codes) is broadcast separately.
    """
    run_id = await _resolve_run_id(body.run_id, session)
    data = body.model_dump(exclude={"run_id"}, exclude_none=True)

    # Flatten scalar data into hash/ prefixed metric keys
    flat_metrics: dict[str, Any] = {}

    # Bit activation rates: list → hash/bit_activation_0, hash/bit_activation_1, ...
    activation_rates = data.get("activation_rates")
    if isinstance(activation_rates, list):
        for i, val in enumerate(activation_rates):
            if isinstance(val, (int, float)):
                flat_metrics[f"hash/bit_activation_{i}"] = val

    # Bit entropy: list → hash/entropy_0, hash/entropy_1, ...
    entropy = data.get("entropy")
    if isinstance(entropy, list):
        for i, val in enumerate(entropy):
            if isinstance(val, (int, float)):
                flat_metrics[f"hash/entropy_{i}"] = val

    # Similarity matrix: NxN → hash/similarity_matrix_size + hash/similarity_0, ...
    similarity_matrix = data.get("similarity_matrix")
    if isinstance(similarity_matrix, list) and len(similarity_matrix) > 0:
        size = len(similarity_matrix)
        flat_metrics["hash/similarity_matrix_size"] = size
        idx = 0
        for row in similarity_matrix:
            if isinstance(row, list):
                for val in row:
                    if isinstance(val, (int, float)):
                        flat_metrics[f"hash/similarity_{idx}"] = val
                        idx += 1

    # Augmentation robustness scores (if present)
    aug_robustness = data.get("augmentation_robustness")
    if isinstance(aug_robustness, dict):
        for key, val in aug_robustness.items():
            if isinstance(val, (int, float)):
                flat_metrics[f"hash/aug_{key}"] = val

    # Ingest flattened scalar metrics through normal pipeline
    if flat_metrics:
        await _ingest(run_id, data.get("step", 0), data.get("epoch", 0), flat_metrics, session)

    # Broadcast non-scalar data (thumbnails, sample codes) as separate message
    samples = data.get("samples")
    if samples and isinstance(samples, list):
        await manager.broadcast(
            run_id,
            {
                "type": "hash_analysis_detail",
                "run_id": run_id,
                "step": data.get("step", 0),
                "epoch": data.get("epoch", 0),
                "samples": samples,
            },
            channel="metrics",
        )

    return {"status": "ok"}


@router.post("/api/checkpoints/register")
async def compat_checkpoint_register(body: CheckpointPayload) -> dict[str, str]:
    """Bridge: MonitorCallback checkpoint registration (ack only)."""
    logger.info(
        "Checkpoint registered: run=%s epoch=%d path=%s",
        body.run_id,
        body.epoch,
        body.path,
    )
    return {"status": "ok"}


@router.post("/api/checkpoints/sync")
async def compat_checkpoint_sync(body: dict[str, Any]) -> dict[str, str]:
    """Bridge: MonitorCallback checkpoint sync (ack only)."""
    return {"status": "ok"}
