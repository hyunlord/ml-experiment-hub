"""Room-based WebSocket connection manager for real-time streaming."""

import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Room-based WebSocket manager.

    Rooms are keyed by (run_id, channel) where channel is one of:
    'metrics', 'system', 'logs'. This allows clients to subscribe
    to specific streams for a given run.
    """

    def __init__(self) -> None:
        """Initialize connection manager."""
        # (run_id, channel) -> list of WebSocket connections
        self._rooms: dict[tuple[int, str], list[WebSocket]] = {}

    async def connect(
        self, websocket: WebSocket, run_id: int, channel: str = "metrics"
    ) -> None:
        """Accept and register a WebSocket to a room."""
        await websocket.accept()
        key = (run_id, channel)
        if key not in self._rooms:
            self._rooms[key] = []
        self._rooms[key].append(websocket)

    def disconnect(
        self, websocket: WebSocket, run_id: int, channel: str = "metrics"
    ) -> None:
        """Remove a WebSocket from a room."""
        key = (run_id, channel)
        if key in self._rooms:
            try:
                self._rooms[key].remove(websocket)
            except ValueError:
                pass
            if not self._rooms[key]:
                del self._rooms[key]

    async def broadcast(
        self, run_id: int, data: dict[str, Any], channel: str = "metrics"
    ) -> None:
        """Send data to all clients in a room."""
        key = (run_id, channel)
        connections = self._rooms.get(key)
        if not connections:
            return

        disconnected: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws, run_id, channel)

    async def send_personal(
        self, websocket: WebSocket, data: dict[str, Any]
    ) -> None:
        """Send data to a single client."""
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    def room_count(self, run_id: int, channel: str = "metrics") -> int:
        """Number of clients in a room."""
        return len(self._rooms.get((run_id, channel), []))


# Global connection manager instance
manager = ConnectionManager()
