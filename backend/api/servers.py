"""REST API endpoints for server management (CRUD + connection test)."""

import logging
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from backend.models.database import async_session_maker
from backend.models.experiment import Server

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/servers", tags=["servers"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ServerCreate(BaseModel):
    """Create a new server."""

    name: str
    host: str
    port: int = 8000
    auth_type: str = "none"
    api_key: str = ""
    description: str = ""
    tags: list[str] = []
    is_default: bool = False
    is_local: bool = False


class ServerUpdate(BaseModel):
    """Update an existing server."""

    name: str | None = None
    host: str | None = None
    port: int | None = None
    auth_type: str | None = None
    api_key: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    is_default: bool | None = None
    is_local: bool | None = None


class ServerResponse(BaseModel):
    """Server response."""

    id: int
    name: str
    host: str
    port: int
    auth_type: str
    api_key: str
    description: str
    tags: list[str]
    is_default: bool
    is_local: bool
    created_at: datetime
    updated_at: datetime


class ConnectionTestResponse(BaseModel):
    """Connection test result."""

    ok: bool
    latency_ms: float | None = None
    error: str | None = None
    agent_version: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ServerResponse])
async def list_servers() -> list[Server]:
    """List all registered servers."""
    async with async_session_maker() as session:
        result = await session.execute(select(Server).order_by(Server.id))
        return list(result.scalars().all())


@router.post("", response_model=ServerResponse, status_code=201)
async def create_server(body: ServerCreate) -> Server:
    """Register a new server."""
    async with async_session_maker() as session:
        server = Server(
            name=body.name,
            host=body.host,
            port=body.port,
            auth_type=body.auth_type,
            api_key=body.api_key,
            description=body.description,
            tags=body.tags,
            is_default=body.is_default,
            is_local=body.is_local,
        )

        # If this is the new default, unset other defaults
        if body.is_default:
            result = await session.execute(
                select(Server).where(Server.is_default == True)  # noqa: E712
            )
            for s in result.scalars().all():
                s.is_default = False

        session.add(server)
        await session.commit()
        await session.refresh(server)
        return server


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(server_id: int) -> Server:
    """Get a single server by ID."""
    async with async_session_maker() as session:
        server = await session.get(Server, server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        return server


@router.put("/{server_id}", response_model=ServerResponse)
async def update_server(server_id: int, body: ServerUpdate) -> Server:
    """Update an existing server."""
    async with async_session_maker() as session:
        server = await session.get(Server, server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        update_data = body.model_dump(exclude_unset=True)

        # If setting as default, unset other defaults
        if update_data.get("is_default"):
            result = await session.execute(
                select(Server).where(
                    Server.is_default == True,  # noqa: E712
                    Server.id != server_id,
                )
            )
            for s in result.scalars().all():
                s.is_default = False

        for key, value in update_data.items():
            setattr(server, key, value)
        server.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(server)
        return server


@router.delete("/{server_id}", status_code=204)
async def delete_server(server_id: int) -> None:
    """Delete a server."""
    async with async_session_maker() as session:
        server = await session.get(Server, server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        await session.delete(server)
        await session.commit()


@router.post("/{server_id}/test", response_model=ConnectionTestResponse)
async def test_connection(server_id: int) -> dict[str, Any]:
    """Test connectivity to a server's agent.

    Pings the server's /agent/health endpoint (or /api/system/health for local).
    """
    async with async_session_maker() as session:
        server = await session.get(Server, server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

    # Build URL
    scheme = "https" if server.port == 443 else "http"
    if server.is_local:
        # Local server — test our own health endpoint
        base_url = f"{scheme}://{server.host}:{server.port}"
        url = f"{base_url}/api/system/health"
    else:
        # Remote server — test agent health endpoint
        base_url = f"{scheme}://{server.host}:{server.port}"
        url = f"{base_url}/agent/health"

    headers: dict[str, str] = {}
    if server.auth_type == "api_key" and server.api_key:
        headers["Authorization"] = f"Bearer {server.api_key}"

    import time

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            latency = round((time.monotonic() - start) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "ok": True,
                    "latency_ms": latency,
                    "agent_version": data.get("version"),
                }
            else:
                return {
                    "ok": False,
                    "latency_ms": latency,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                }
    except httpx.ConnectError:
        return {"ok": False, "error": "Connection refused"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Connection timed out (10s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
