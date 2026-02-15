"""ML Experiment Hub — Lightweight Remote Agent.

A minimal FastAPI server that exposes system metrics for remote monitoring.
Install: pip install fastapi uvicorn psutil
Run:     python main.py --port 8001

The hub backend connects to this agent to collect remote server stats.
"""

import argparse
import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from collector import collect_system_info

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml-hub-agent")

app = FastAPI(title="ML Experiment Hub Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/agent/health")
async def health() -> dict[str, str]:
    """Health check — used by hub to verify connectivity."""
    return {"status": "ok", "agent": "ml-experiment-hub-agent", "version": "0.1.0"}


@app.get("/agent/system")
async def system_info() -> dict[str, Any]:
    """Full system information snapshot."""
    return await collect_system_info()


@app.get("/agent/gpu")
async def gpu_info() -> dict[str, Any]:
    """GPU-specific information."""
    info = await collect_system_info()
    return {
        "gpus": info.get("gpus", []),
        "gpu_available": len(info.get("gpus", [])) > 0,
    }


@app.websocket("/agent/ws/system")
async def ws_system(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time system stats streaming."""
    await websocket.accept()
    logger.info("WebSocket client connected")
    try:
        while True:
            info = await collect_system_info()
            await websocket.send_text(json.dumps(info, default=str))
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket error")


def main() -> None:
    """Entry point for CLI usage."""
    parser = argparse.ArgumentParser(description="ML Experiment Hub Agent")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8001, help="Bind port")
    args = parser.parse_args()

    import uvicorn

    logger.info("Starting agent on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
