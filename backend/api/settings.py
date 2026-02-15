"""REST API endpoints for hub settings (webhook, concurrency)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_session
from backend.schemas.project import (
    GitCredentialCreate,
    GitCredentialListResponse,
    GitCredentialResponse,
)
from backend.services.git_credential_service import GitCredentialService
from backend.services.notifier import get_hub_settings, test_webhook, update_hub_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class HubSettingsResponse(BaseModel):
    """Hub settings response."""

    discord_webhook_url: str = ""
    slack_webhook_url: str = ""
    max_concurrent_runs: int = 1


class UpdateSettingsRequest(BaseModel):
    """Update hub settings."""

    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None
    max_concurrent_runs: int | None = None


class TestWebhookRequest(BaseModel):
    """Test webhook request."""

    provider: str = "discord"  # "discord" or "slack"


class TestWebhookResponse(BaseModel):
    """Test webhook response."""

    ok: bool
    error: str | None = None


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
    if body.slack_webhook_url is not None:
        updates["slack_webhook_url"] = body.slack_webhook_url
    if body.max_concurrent_runs is not None:
        updates["max_concurrent_runs"] = max(1, body.max_concurrent_runs)
    data = update_hub_settings(updates)
    return HubSettingsResponse(**data)


@router.post("/test-webhook", response_model=TestWebhookResponse)
async def post_test_webhook(body: TestWebhookRequest) -> TestWebhookResponse:
    """Send a test message to the configured webhook."""
    result = await test_webhook(body.provider)
    return TestWebhookResponse(**result)


@router.get("/git-credentials", response_model=GitCredentialListResponse)
async def list_git_credentials(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GitCredentialListResponse:
    """List all stored git credentials (tokens masked)."""
    service = GitCredentialService(session)
    creds = await service.list_credentials()
    return GitCredentialListResponse(credentials=creds)


@router.post("/git-credentials", response_model=GitCredentialResponse, status_code=201)
async def create_git_credential(
    data: GitCredentialCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GitCredentialResponse:
    """Store a new git credential."""
    service = GitCredentialService(session)
    return await service.create_credential(data)


@router.delete("/git-credentials/{credential_id}", status_code=204)
async def delete_git_credential(
    credential_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete a git credential."""
    service = GitCredentialService(session)
    deleted = await service.delete_credential(credential_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential not found")
