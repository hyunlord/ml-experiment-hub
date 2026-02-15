"""Notification service for experiment lifecycle events.

Sends notifications via:
- WebSocket broadcast (browser Notification API on the frontend)
- Discord webhook (when configured)

Webhook URL is stored in a JSON settings file on disk.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

# Persistent settings file for webhook URL and concurrency
_SETTINGS_PATH = Path(settings.DATA_DIR) / "hub_settings.json"


def _load_settings() -> dict[str, Any]:
    """Load persisted hub settings from disk."""
    if _SETTINGS_PATH.exists():
        try:
            return json.loads(_SETTINGS_PATH.read_text())
        except Exception:
            logger.warning("Failed to read settings file, using defaults")
    return {}


def _save_settings(data: dict[str, Any]) -> None:
    """Save hub settings to disk."""
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(data, indent=2))


def get_hub_settings() -> dict[str, Any]:
    """Get all hub settings."""
    defaults: dict[str, Any] = {
        "discord_webhook_url": "",
        "slack_webhook_url": "",
        "max_concurrent_runs": 1,
    }
    saved = _load_settings()
    return {**defaults, **saved}


def update_hub_settings(updates: dict[str, Any]) -> dict[str, Any]:
    """Update hub settings (merge with existing)."""
    current = get_hub_settings()
    current.update(updates)
    _save_settings(current)
    return current


async def send_ws_notification(
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Broadcast a notification event to all connected WS clients.

    Uses run_id=0, channel='notifications' as a global notification room.
    Frontend subscribes to this room to show browser Notification API popups.
    """
    from backend.api.websocket import manager

    await manager.broadcast(
        0,
        {"type": event_type, **data},
        channel="notifications",
    )


async def send_discord_webhook(
    title: str,
    description: str,
    color: int = 0x00FF00,
    fields: list[dict[str, str]] | None = None,
) -> None:
    """Send a message to Discord via webhook.

    Args:
        title: Embed title.
        description: Embed description.
        color: Embed color (green=success, red=failure).
        fields: Optional embed fields [{name, value, inline}].
    """
    hub_settings = get_hub_settings()
    webhook_url = hub_settings.get("discord_webhook_url", "")
    if not webhook_url:
        return  # No webhook configured — silently skip

    embed: dict[str, Any] = {
        "title": title,
        "description": description,
        "color": color,
    }
    if fields:
        embed["fields"] = fields

    payload = {"embeds": [embed]}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=payload, timeout=10.0)
            resp.raise_for_status()
            logger.info("Discord webhook sent: %s", title)
    except Exception:
        logger.warning("Failed to send Discord webhook: %s", title)


async def send_slack_webhook(
    text: str,
    blocks: list[dict[str, Any]] | None = None,
) -> None:
    """Send a message to Slack via incoming webhook.

    Args:
        text: Fallback text for notifications.
        blocks: Optional Slack Block Kit blocks for rich formatting.
    """
    hub_settings = get_hub_settings()
    webhook_url = hub_settings.get("slack_webhook_url", "")
    if not webhook_url:
        return  # No webhook configured — silently skip

    payload: dict[str, Any] = {"text": text}
    if blocks:
        payload["blocks"] = blocks

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=payload, timeout=10.0)
            resp.raise_for_status()
            logger.info("Slack webhook sent: %s", text[:80])
    except Exception:
        logger.warning("Failed to send Slack webhook: %s", text[:80])


async def test_webhook(provider: str = "discord") -> dict[str, Any]:
    """Send a test message to the configured webhook.

    Args:
        provider: 'discord' or 'slack'.

    Returns:
        dict with 'ok' bool and optional 'error' message.
    """
    hub_settings = get_hub_settings()

    if provider == "discord":
        url = hub_settings.get("discord_webhook_url", "")
        if not url:
            return {"ok": False, "error": "Discord webhook URL not configured"}
        try:
            await send_discord_webhook(
                title="Test Notification",
                description="This is a test message from ML Experiment Hub.",
                color=0x9B59B6,  # purple
                fields=[{"name": "Status", "value": "Webhook is working!", "inline": "true"}],
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif provider == "slack":
        url = hub_settings.get("slack_webhook_url", "")
        if not url:
            return {"ok": False, "error": "Slack webhook URL not configured"}
        try:
            await send_slack_webhook(
                text="Test Notification from ML Experiment Hub - Webhook is working!",
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": f"Unknown provider: {provider}"}


async def notify_run_started(
    experiment_name: str,
    run_id: int,
) -> None:
    """Notify that a training run has started."""
    # WebSocket notification
    await send_ws_notification(
        "run_started",
        {
            "experiment_name": experiment_name,
            "run_id": run_id,
            "message": f"Training started: {experiment_name}",
        },
    )

    # Discord webhook
    await send_discord_webhook(
        title="Training Started",
        description=f"**{experiment_name}** (Run #{run_id})",
        color=0x3498DB,  # blue
    )

    # Slack webhook
    await send_slack_webhook(
        text=f":arrow_forward: *Training Started*: {experiment_name} (Run #{run_id})",
    )


async def notify_run_completed(
    experiment_name: str,
    run_id: int,
    metrics_summary: dict[str, Any] | None = None,
    duration_seconds: float | None = None,
) -> None:
    """Notify that a training run completed successfully."""
    duration_str = ""
    if duration_seconds is not None:
        mins = int(duration_seconds // 60)
        secs = int(duration_seconds % 60)
        duration_str = f"{mins}m {secs}s"

    # Format metrics for display
    metrics_display = ""
    if metrics_summary:
        metric_lines = []
        for k, v in metrics_summary.items():
            if k.startswith("_"):
                continue
            if isinstance(v, float):
                metric_lines.append(f"  {k}: {v:.4f}")
            else:
                metric_lines.append(f"  {k}: {v}")
        if metric_lines:
            metrics_display = "\n".join(metric_lines[:10])  # limit to 10 lines

    # WebSocket notification
    await send_ws_notification(
        "run_completed",
        {
            "experiment_name": experiment_name,
            "run_id": run_id,
            "message": f"Training completed: {experiment_name}",
            "duration": duration_str,
            "metrics": metrics_summary or {},
        },
    )

    # Discord webhook
    fields: list[dict[str, str]] = []
    if duration_str:
        fields.append({"name": "Duration", "value": duration_str, "inline": "true"})
    if metrics_display:
        fields.append(
            {"name": "Final Metrics", "value": f"```\n{metrics_display}\n```", "inline": "false"}
        )

    await send_discord_webhook(
        title="Training Completed",
        description=f"**{experiment_name}** (Run #{run_id})",
        color=0x2ECC71,  # green
        fields=fields,
    )

    # Slack webhook
    slack_parts = [f":white_check_mark: *Training Completed*: {experiment_name} (Run #{run_id})"]
    if duration_str:
        slack_parts.append(f"Duration: {duration_str}")
    if metrics_display:
        slack_parts.append(f"```{metrics_display}```")
    await send_slack_webhook(text="\n".join(slack_parts))


async def notify_run_failed(
    experiment_name: str,
    run_id: int,
    duration_seconds: float | None = None,
    last_log_lines: str | None = None,
) -> None:
    """Notify that a training run failed."""
    duration_str = ""
    if duration_seconds is not None:
        mins = int(duration_seconds // 60)
        secs = int(duration_seconds % 60)
        duration_str = f"{mins}m {secs}s"

    # WebSocket notification
    await send_ws_notification(
        "run_failed",
        {
            "experiment_name": experiment_name,
            "run_id": run_id,
            "message": f"Training failed: {experiment_name}",
            "duration": duration_str,
            "last_log": last_log_lines or "",
        },
    )

    # Discord webhook
    fields: list[dict[str, str]] = []
    if duration_str:
        fields.append({"name": "Duration", "value": duration_str, "inline": "true"})
    if last_log_lines:
        # Truncate to fit Discord embed limits
        truncated = last_log_lines[:1000]
        fields.append(
            {"name": "Last Log Lines", "value": f"```\n{truncated}\n```", "inline": "false"}
        )

    await send_discord_webhook(
        title="Training Failed",
        description=f"**{experiment_name}** (Run #{run_id})",
        color=0xE74C3C,  # red
        fields=fields,
    )

    # Slack webhook
    slack_parts = [f":x: *Training Failed*: {experiment_name} (Run #{run_id})"]
    if duration_str:
        slack_parts.append(f"Duration: {duration_str}")
    if last_log_lines:
        truncated = last_log_lines[:500]
        slack_parts.append(f"```{truncated}```")
    await send_slack_webhook(text="\n".join(slack_parts))
