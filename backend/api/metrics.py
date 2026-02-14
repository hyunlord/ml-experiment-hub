"""Metrics API: HTTP collection, REST queries, and WebSocket streaming."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.api.websocket import manager
from backend.core.lttb import downsample_lttb
from backend.models.database import get_session
from backend.models.experiment import ExperimentRun, MetricLog, SystemStats

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class MetricIngest(BaseModel):
    """Body for POST /api/runs/{run_id}/metrics (from training process)."""

    step: int = Field(ge=0)
    epoch: float | None = None
    metrics: dict[str, Any]


class MetricPointResponse(BaseModel):
    """Single metric data point in query response."""

    step: int
    epoch: int | None
    timestamp: datetime
    metrics: dict[str, Any]


class MetricsQueryResponse(BaseModel):
    """Response for GET /api/runs/{run_id}/metrics."""

    run_id: int
    total: int
    data: list[MetricPointResponse]


class SystemStatsIngest(BaseModel):
    """Body for POST /api/runs/{run_id}/system."""
    gpu_util: float | None = None
    gpu_memory_used: float | None = None
    gpu_memory_total: float | None = None
    cpu_percent: float | None = None
    ram_percent: float | None = None
    # Multi-GPU support
    gpus: list[dict[str, Any]] | None = None


# ---------------------------------------------------------------------------
# HTTP Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/runs/{run_id}/metrics", status_code=201)
async def ingest_metrics(
    run_id: int,
    body: MetricIngest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Receive metrics from a training process and broadcast via WebSocket.

    This endpoint is called by the training script (or MonitorCallback)
    to push metrics to the server in real time.
    """
    # Verify run exists
    result = await session.execute(
        select(ExperimentRun).where(ExperimentRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Persist to DB
    log_entry = MetricLog(
        run_id=run_id,
        step=body.step,
        epoch=int(body.epoch) if body.epoch is not None else None,
        metrics_json=body.metrics,
        timestamp=datetime.utcnow(),
    )
    session.add(log_entry)
    await session.commit()

    # Broadcast to WebSocket clients watching this run's metrics
    await manager.broadcast(
        run_id,
        {
            "type": "metric",
            "run_id": run_id,
            "step": body.step,
            "epoch": body.epoch,
            "metrics": body.metrics,
            "timestamp": datetime.utcnow().isoformat(),
        },
        channel="metrics",
    )

    return {"status": "ok"}


@router.post("/api/runs/{run_id}/system", status_code=201)
async def ingest_system_stats(
    run_id: int,
    body: SystemStatsIngest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Receive system stats from training process or system monitor."""
    # Verify run exists
    result = await session.execute(
        select(ExperimentRun).where(ExperimentRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # For multi-GPU, store primary GPU stats in DB
    gpu_util = body.gpu_util
    gpu_mem_used = body.gpu_memory_used
    gpu_mem_total = body.gpu_memory_total
    if body.gpus and len(body.gpus) > 0:
        primary = body.gpus[0]
        gpu_util = gpu_util or primary.get("util")
        gpu_mem_used = gpu_mem_used or primary.get("memory_used_mb")
        gpu_mem_total = gpu_mem_total or primary.get("memory_total_mb")

    stat = SystemStats(
        run_id=run_id,
        timestamp=datetime.utcnow(),
        gpu_util=gpu_util,
        gpu_memory_used=gpu_mem_used,
        gpu_memory_total=gpu_mem_total,
        cpu_percent=body.cpu_percent,
        ram_percent=body.ram_percent,
    )
    session.add(stat)
    await session.commit()

    # Broadcast via WebSocket
    ws_data: dict[str, Any] = {
        "type": "system_stats",
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat(),
        "gpu_util": gpu_util,
        "gpu_memory_used": gpu_mem_used,
        "gpu_memory_total": gpu_mem_total,
        "cpu_percent": body.cpu_percent,
        "ram_percent": body.ram_percent,
    }
    if body.gpus:
        ws_data["gpus"] = body.gpus

    await manager.broadcast(run_id, ws_data, channel="system")

    return {"status": "ok"}


@router.get("/api/runs/{run_id}/metrics", response_model=MetricsQueryResponse)
async def query_metrics(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    keys: str | None = Query(default=None, description="Comma-separated metric keys to filter"),
    downsample: int | None = Query(default=None, ge=3, le=10000, description="Target points via LTTB"),
) -> MetricsQueryResponse:
    """Query stored metrics for a run with optional key filtering and downsampling."""
    # Verify run exists
    result = await session.execute(
        select(ExperimentRun).where(ExperimentRun.id == run_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Fetch all metric logs ordered by step
    result = await session.execute(
        select(MetricLog)
        .where(MetricLog.run_id == run_id)
        .order_by(MetricLog.step)
    )
    logs = result.scalars().all()

    # Filter by keys if specified
    key_set = {k.strip() for k in keys.split(",")} if keys else None

    data: list[dict[str, Any]] = []
    for log in logs:
        metrics = log.metrics_json or {}
        if key_set:
            metrics = {k: v for k, v in metrics.items() if k in key_set}
            if not metrics:
                continue

        data.append({
            "step": log.step,
            "epoch": log.epoch,
            "timestamp": log.timestamp.isoformat(),
            "metrics": metrics,
        })

    total = len(data)

    # Downsample if requested and data exceeds threshold
    if downsample and len(data) > downsample:
        # For LTTB, pick the first metric key as y-axis
        first_key = None
        if data:
            first_key = next(iter(data[0]["metrics"]), None)

        if first_key:
            # Flatten for LTTB: use step as x, first metric as y
            lttb_data = [
                {"step": d["step"], "_y": d["metrics"].get(first_key, 0), "_idx": i}
                for i, d in enumerate(data)
            ]
            sampled = downsample_lttb(lttb_data, downsample, x_key="step", y_key="_y")
            sampled_indices = {d["_idx"] for d in sampled}
            data = [d for i, d in enumerate(data) if i in sampled_indices]

    return MetricsQueryResponse(
        run_id=run_id,
        total=total,
        data=[
            MetricPointResponse(
                step=d["step"],
                epoch=d["epoch"],
                timestamp=d["timestamp"],
                metrics=d["metrics"],
            )
            for d in data
        ],
    )


# ---------------------------------------------------------------------------
# WebSocket Endpoints
# ---------------------------------------------------------------------------

@router.websocket("/ws/runs/{run_id}/metrics")
async def ws_metrics(websocket: WebSocket, run_id: int) -> None:
    """Stream metrics for a run in real time.

    On connect, sends the last N metric logs as catch-up,
    then new metrics are pushed as they arrive via broadcast.
    """
    await manager.connect(websocket, run_id, channel="metrics")
    try:
        # Send catch-up: last 50 metrics
        async with _get_session_ctx() as session:
            result = await session.execute(
                select(MetricLog)
                .where(MetricLog.run_id == run_id)
                .order_by(MetricLog.step.desc())
                .limit(50)
            )
            recent = list(reversed(result.scalars().all()))

            for log in recent:
                await manager.send_personal(websocket, {
                    "type": "metric",
                    "run_id": run_id,
                    "step": log.step,
                    "epoch": log.epoch,
                    "metrics": log.metrics_json,
                    "timestamp": log.timestamp.isoformat(),
                })

        # Keep alive — new metrics arrive via broadcast from ingest endpoint
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
            except asyncio.TimeoutError:
                await manager.send_personal(websocket, {"type": "keepalive"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket metrics error for run %d", run_id)
    finally:
        manager.disconnect(websocket, run_id, channel="metrics")


@router.websocket("/ws/runs/{run_id}/system")
async def ws_system(websocket: WebSocket, run_id: int) -> None:
    """Stream GPU/CPU/RAM system stats for a run.

    Polls SystemStats table every second and pushes new entries.
    """
    await manager.connect(websocket, run_id, channel="system")
    last_id = 0
    try:
        while True:
            try:
                async with _get_session_ctx() as session:
                    result = await session.execute(
                        select(SystemStats)
                        .where(SystemStats.run_id == run_id)
                        .where(SystemStats.id > last_id)
                        .order_by(SystemStats.id)
                        .limit(10)
                    )
                    stats = result.scalars().all()

                    for stat in stats:
                        await manager.send_personal(websocket, {
                            "type": "system_stats",
                            "run_id": run_id,
                            "timestamp": stat.timestamp.isoformat(),
                            "gpu_util": stat.gpu_util,
                            "gpu_memory_used": stat.gpu_memory_used,
                            "gpu_memory_total": stat.gpu_memory_total,
                            "cpu_percent": stat.cpu_percent,
                            "ram_percent": stat.ram_percent,
                        })
                        last_id = stat.id  # type: ignore[assignment]

                # Check for client messages (ping/disconnect)
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                    if data == "ping":
                        await manager.send_personal(websocket, {"type": "pong"})
                except asyncio.TimeoutError:
                    pass  # Normal — just poll again

            except WebSocketDisconnect:
                break
    except Exception:
        logger.exception("WebSocket system error for run %d", run_id)
    finally:
        manager.disconnect(websocket, run_id, channel="system")


@router.websocket("/ws/runs/{run_id}/logs")
async def ws_logs(websocket: WebSocket, run_id: int) -> None:
    """Stream training process stdout/stderr in real time (tail -f style).

    Reads the log file associated with the run and streams new lines.
    """
    await manager.connect(websocket, run_id, channel="logs")
    try:
        # Find log path from ExperimentRun
        async with _get_session_ctx() as session:
            result = await session.execute(
                select(ExperimentRun).where(ExperimentRun.id == run_id)
            )
            run = result.scalar_one_or_none()

        log_path = Path(run.log_path) if run and run.log_path else None

        if not log_path or not log_path.exists():
            await manager.send_personal(websocket, {
                "type": "log",
                "run_id": run_id,
                "line": "[No log file available]",
            })
            # Still keep connection alive for future logs
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    if data == "ping":
                        await manager.send_personal(websocket, {"type": "pong"})
                except asyncio.TimeoutError:
                    await manager.send_personal(websocket, {"type": "keepalive"})
        else:
            # Tail the log file
            with open(log_path) as f:
                # Send last 100 lines as catch-up
                lines = f.readlines()
                for line in lines[-100:]:
                    await manager.send_personal(websocket, {
                        "type": "log",
                        "run_id": run_id,
                        "line": line.rstrip("\n"),
                    })

                # Stream new lines as they appear
                while True:
                    line = f.readline()
                    if line:
                        await manager.send_personal(websocket, {
                            "type": "log",
                            "run_id": run_id,
                            "line": line.rstrip("\n"),
                        })
                    else:
                        # No new line — check for client messages
                        try:
                            data = await asyncio.wait_for(
                                websocket.receive_text(), timeout=0.5
                            )
                            if data == "ping":
                                await manager.send_personal(
                                    websocket, {"type": "pong"}
                                )
                        except asyncio.TimeoutError:
                            pass

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket logs error for run %d", run_id)
    finally:
        manager.disconnect(websocket, run_id, channel="logs")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from backend.models.database import async_session_maker


@asynccontextmanager
async def _get_session_ctx() -> AsyncGenerator[AsyncSession, None]:
    """Create a standalone async session for WebSocket handlers.

    WebSocket handlers run outside the normal request lifecycle,
    so they need their own session management.
    """
    async with async_session_maker() as session:
        yield session
