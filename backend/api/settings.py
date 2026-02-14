"""REST API endpoints for hub settings (webhook, concurrency)."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.notifier import get_hub_settings, update_hub_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class HubSettingsResponse(BaseModel):
    """Hub settings response."""

    discord_webhook_url: str = ""
    max_concurrent_runs: int = 1


class UpdateSettingsRequest(BaseModel):
    """Update hub settings."""

    discord_webhook_url: str | None = None
    max_concurrent_runs: int | None = None


@router.get("", response_model=HubSettingsResponse)
async def get_settings() -> HubSettingsResponse:
    """Get current hub settings."""
    data = get_hub_settings()
    return HubSettingsResponse(**data)


@router.put("", response_model=HubSettingsResponse)
async def put_settings(body: UpdateSettingsRequest) -> HubSettingsResponse:
    """Update hub settings."""
    updates: dict[str, Any] = {}
    if body.discord_webhook_url is not None:
        updates["discord_webhook_url"] = body.discord_webhook_url
    if body.max_concurrent_runs is not None:
        updates["max_concurrent_runs"] = max(1, body.max_concurrent_runs)
    data = update_hub_settings(updates)
    return HubSettingsResponse(**data)
