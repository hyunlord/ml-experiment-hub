"""WebSocket endpoint for streaming experiment metrics."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time metric streaming."""

    def __init__(self) -> None:
        """Initialize connection manager."""
        # experiment_id -> list of WebSocket connections
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, experiment_id: int) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        if experiment_id not in self.active_connections:
            self.active_connections[experiment_id] = []
        self.active_connections[experiment_id].append(websocket)

    def disconnect(self, websocket: WebSocket, experiment_id: int) -> None:
        """Remove a WebSocket connection."""
        if experiment_id in self.active_connections:
            self.active_connections[experiment_id].remove(websocket)
            if not self.active_connections[experiment_id]:
                del self.active_connections[experiment_id]

    async def broadcast(self, experiment_id: int, message: dict[str, Any]) -> None:
        """Broadcast a message to all connections for an experiment."""
        if experiment_id not in self.active_connections:
            return

        disconnected: list[WebSocket] = []
        for connection in self.active_connections[experiment_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket, experiment_id)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/experiments/{experiment_id}/metrics")
async def websocket_endpoint(websocket: WebSocket, experiment_id: int) -> None:
    """WebSocket endpoint for streaming experiment metrics in real-time."""
    await manager.connect(websocket, experiment_id)
    try:
        # Keep connection alive and listen for client messages
        while True:
            try:
                # Receive message from client (ping/pong or commands)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Echo back for keepalive
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"type": "keepalive"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, experiment_id)
    except Exception:
        manager.disconnect(websocket, experiment_id)
