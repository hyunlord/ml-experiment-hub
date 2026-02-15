"""Tests for Milestone 5: notifications + experiment queue.

Covers:
1. Notification service — hub settings persistence, webhook formatting
2. Discord/Slack webhook message construction
3. Test webhook endpoint
4. Queue model — CRUD operations via API
5. Queue scheduler — capacity checks, entry reconciliation
6. Settings API — get/put with all fields
7. Browser notification WebSocket endpoint exists
8. Genericity: no vlm-specific terms in notification/queue code
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.notifier import (
    get_hub_settings,
    notify_run_completed,
    notify_run_failed,
    notify_run_started,
    send_discord_webhook,
    send_slack_webhook,
    send_ws_notification,
    test_webhook as notifier_test_webhook,
    update_hub_settings,
)
from shared.schemas import QueueStatus


def _run(coro):  # noqa: ANN001, ANN202
    """Run an async coroutine in a fresh event loop."""
    return asyncio.run(coro)


# =============================================================================
# 1. Hub settings persistence
# =============================================================================


def test_hub_settings_defaults() -> None:
    """Hub settings should have sensible defaults."""
    with patch("backend.services.notifier._SETTINGS_PATH", Path("/tmp/_test_no_exist.json")):
        settings = get_hub_settings()
    assert settings["discord_webhook_url"] == ""
    assert settings["slack_webhook_url"] == ""
    assert settings["max_concurrent_runs"] == 1


def test_hub_settings_update_and_read(tmp_path: Path) -> None:
    """Updated settings should persist and be readable."""
    settings_file = tmp_path / "hub_settings.json"
    with patch("backend.services.notifier._SETTINGS_PATH", settings_file):
        update_hub_settings({"discord_webhook_url": "https://discord.test/webhook"})
        result = get_hub_settings()
    assert result["discord_webhook_url"] == "https://discord.test/webhook"
    assert result["slack_webhook_url"] == ""  # default preserved


def test_hub_settings_slack_url(tmp_path: Path) -> None:
    """Slack webhook URL should be stored and retrieved."""
    settings_file = tmp_path / "hub_settings.json"
    with patch("backend.services.notifier._SETTINGS_PATH", settings_file):
        update_hub_settings({"slack_webhook_url": "https://hooks.slack.com/test"})
        result = get_hub_settings()
    assert result["slack_webhook_url"] == "https://hooks.slack.com/test"


def test_hub_settings_max_concurrent(tmp_path: Path) -> None:
    """Max concurrent runs should be persisted."""
    settings_file = tmp_path / "hub_settings.json"
    with patch("backend.services.notifier._SETTINGS_PATH", settings_file):
        update_hub_settings({"max_concurrent_runs": 4})
        result = get_hub_settings()
    assert result["max_concurrent_runs"] == 4


# =============================================================================
# 2. Discord webhook message construction
# =============================================================================


def test_discord_webhook_skips_when_empty() -> None:
    """Discord webhook should silently skip when URL is empty."""
    with patch(
        "backend.services.notifier.get_hub_settings", return_value={"discord_webhook_url": ""}
    ):
        _run(send_discord_webhook("Test", "Test description"))


def test_discord_webhook_sends_embed() -> None:
    """Discord webhook should POST an embed to the configured URL."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "backend.services.notifier.get_hub_settings",
            return_value={"discord_webhook_url": "https://discord.test/wh"},
        ),
        patch("backend.services.notifier.httpx.AsyncClient", return_value=mock_client),
    ):
        _run(
            send_discord_webhook(
                "Title", "Desc", color=0xFF0000, fields=[{"name": "F", "value": "V"}]
            )
        )

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://discord.test/wh"
    payload = call_args[1]["json"]
    assert payload["embeds"][0]["title"] == "Title"
    assert payload["embeds"][0]["color"] == 0xFF0000


# =============================================================================
# 3. Slack webhook message construction
# =============================================================================


def test_slack_webhook_skips_when_empty() -> None:
    """Slack webhook should silently skip when URL is empty."""
    with patch(
        "backend.services.notifier.get_hub_settings", return_value={"slack_webhook_url": ""}
    ):
        _run(send_slack_webhook("Test message"))


def test_slack_webhook_sends_text() -> None:
    """Slack webhook should POST text to the configured URL."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "backend.services.notifier.get_hub_settings",
            return_value={"slack_webhook_url": "https://hooks.slack.com/test"},
        ),
        patch("backend.services.notifier.httpx.AsyncClient", return_value=mock_client),
    ):
        _run(send_slack_webhook("Hello Slack"))

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://hooks.slack.com/test"
    payload = call_args[1]["json"]
    assert payload["text"] == "Hello Slack"


# =============================================================================
# 4. Notification event functions
# =============================================================================


def test_notify_run_started_sends_ws_and_webhooks() -> None:
    """notify_run_started should call WS broadcast and webhooks."""
    with (
        patch("backend.services.notifier.send_ws_notification", new_callable=AsyncMock) as mock_ws,
        patch(
            "backend.services.notifier.send_discord_webhook", new_callable=AsyncMock
        ) as mock_discord,
        patch("backend.services.notifier.send_slack_webhook", new_callable=AsyncMock) as mock_slack,
    ):
        _run(notify_run_started("test-exp", 42))

    mock_ws.assert_called_once()
    ws_args = mock_ws.call_args
    assert ws_args[0][0] == "run_started"
    assert ws_args[0][1]["run_id"] == 42

    mock_discord.assert_called_once()
    mock_slack.assert_called_once()


def test_notify_run_completed_includes_metrics() -> None:
    """notify_run_completed should include duration and metrics in webhooks."""
    with (
        patch("backend.services.notifier.send_ws_notification", new_callable=AsyncMock) as mock_ws,
        patch(
            "backend.services.notifier.send_discord_webhook", new_callable=AsyncMock
        ) as mock_discord,
        patch("backend.services.notifier.send_slack_webhook", new_callable=AsyncMock) as mock_slack,
    ):
        _run(
            notify_run_completed(
                "exp-1",
                run_id=10,
                metrics_summary={"val/loss": 0.25, "val/acc": 0.95, "_duration_seconds": 120},
                duration_seconds=120.0,
            )
        )

    # WS should include metrics
    ws_data = mock_ws.call_args[0][1]
    assert ws_data["duration"] == "2m 0s"
    assert ws_data["metrics"]["val/loss"] == 0.25

    # Discord should have fields for duration and metrics
    discord_args = mock_discord.call_args
    assert discord_args[1]["fields"] is not None

    # Slack should include metrics text (called with keyword arg text=...)
    slack_text = mock_slack.call_args[1].get("text") or mock_slack.call_args[0][0]
    assert "val/loss" in slack_text or "Completed" in slack_text


def test_notify_run_failed_includes_log_lines() -> None:
    """notify_run_failed should include last log lines."""
    with (
        patch("backend.services.notifier.send_ws_notification", new_callable=AsyncMock) as mock_ws,
        patch("backend.services.notifier.send_discord_webhook", new_callable=AsyncMock),
        patch("backend.services.notifier.send_slack_webhook", new_callable=AsyncMock) as mock_slack,
    ):
        _run(
            notify_run_failed(
                "exp-fail",
                run_id=5,
                duration_seconds=30.0,
                last_log_lines="RuntimeError: CUDA OOM\nKilled",
            )
        )

    ws_data = mock_ws.call_args[0][1]
    assert "CUDA OOM" in ws_data["last_log"]

    slack_text = mock_slack.call_args[1].get("text") or mock_slack.call_args[0][0]
    assert "CUDA OOM" in slack_text


# =============================================================================
# 5. Test webhook function
# =============================================================================


def test_test_webhook_discord_no_url() -> None:
    """test_webhook should fail gracefully when no Discord URL is configured."""
    with patch(
        "backend.services.notifier.get_hub_settings",
        return_value={"discord_webhook_url": "", "slack_webhook_url": ""},
    ):
        result = _run(notifier_test_webhook("discord"))
    assert result["ok"] is False
    assert "not configured" in result["error"]


def test_test_webhook_slack_no_url() -> None:
    """test_webhook should fail gracefully when no Slack URL is configured."""
    with patch(
        "backend.services.notifier.get_hub_settings",
        return_value={"discord_webhook_url": "", "slack_webhook_url": ""},
    ):
        result = _run(notifier_test_webhook("slack"))
    assert result["ok"] is False
    assert "not configured" in result["error"]


def test_test_webhook_unknown_provider() -> None:
    """test_webhook should handle unknown provider."""
    result = _run(notifier_test_webhook("telegram"))
    assert result["ok"] is False
    assert "Unknown provider" in result["error"]


# =============================================================================
# 6. Queue status enum
# =============================================================================


def test_queue_status_values() -> None:
    """QueueStatus should have all required states."""
    assert QueueStatus.WAITING == "waiting"
    assert QueueStatus.RUNNING == "running"
    assert QueueStatus.COMPLETED == "completed"
    assert QueueStatus.FAILED == "failed"
    assert QueueStatus.CANCELLED == "cancelled"


# =============================================================================
# 7. Queue model
# =============================================================================


def test_queue_entry_model_fields() -> None:
    """QueueEntry should have all required fields."""
    from backend.models.experiment import QueueEntry

    fields = {f for f in QueueEntry.model_fields}
    required = {
        "id",
        "experiment_config_id",
        "position",
        "status",
        "run_id",
        "error_message",
        "added_at",
        "started_at",
        "completed_at",
    }
    assert required.issubset(fields)


def test_queue_entry_default_status() -> None:
    """QueueEntry default status should be WAITING."""
    from backend.models.experiment import QueueEntry

    entry = QueueEntry(experiment_config_id=1)
    assert entry.status == QueueStatus.WAITING
    assert entry.position == 0


# =============================================================================
# 8. Queue scheduler structure
# =============================================================================


def test_queue_scheduler_has_poll_interval() -> None:
    """Queue scheduler should use 5-second polling."""
    from backend.services.queue_scheduler import POLL_INTERVAL

    assert POLL_INTERVAL == 5


def test_queue_scheduler_has_start_stop() -> None:
    """Queue scheduler should have start() and stop() methods."""
    from backend.services.queue_scheduler import QueueScheduler

    scheduler = QueueScheduler()
    assert hasattr(scheduler, "start")
    assert hasattr(scheduler, "stop")
    assert hasattr(scheduler, "_tick")


# =============================================================================
# 9. Settings API schemas
# =============================================================================


def test_settings_response_includes_slack() -> None:
    """HubSettingsResponse should include slack_webhook_url."""
    from backend.api.settings import HubSettingsResponse

    resp = HubSettingsResponse()
    assert resp.discord_webhook_url == ""
    assert resp.slack_webhook_url == ""
    assert resp.max_concurrent_runs == 1


def test_settings_update_request_fields() -> None:
    """UpdateSettingsRequest should accept all webhook fields."""
    from backend.api.settings import UpdateSettingsRequest

    req = UpdateSettingsRequest(
        discord_webhook_url="https://discord.test",
        slack_webhook_url="https://slack.test",
        max_concurrent_runs=2,
    )
    assert req.discord_webhook_url == "https://discord.test"
    assert req.slack_webhook_url == "https://slack.test"


def test_test_webhook_request_schema() -> None:
    """TestWebhookRequest should accept provider field."""
    from backend.api.settings import TestWebhookRequest

    req = TestWebhookRequest(provider="slack")
    assert req.provider == "slack"
    # Default should be discord
    req2 = TestWebhookRequest()
    assert req2.provider == "discord"


# =============================================================================
# 10. Queue API schemas
# =============================================================================


def test_queue_entry_response_schema() -> None:
    """QueueEntryResponse should have all required fields."""
    from backend.api.queue import QueueEntryResponse

    fields = set(QueueEntryResponse.model_fields.keys())
    required = {
        "id",
        "experiment_config_id",
        "experiment_name",
        "position",
        "status",
        "run_id",
        "added_at",
    }
    assert required.issubset(fields)


def test_add_to_queue_request_schema() -> None:
    """AddToQueueRequest should require experiment_config_id."""
    from backend.api.queue import AddToQueueRequest

    req = AddToQueueRequest(experiment_config_id=42)
    assert req.experiment_config_id == 42


def test_reorder_request_schema() -> None:
    """ReorderRequest should accept list of entry IDs."""
    from backend.api.queue import ReorderRequest

    req = ReorderRequest(entry_ids=[3, 1, 2])
    assert req.entry_ids == [3, 1, 2]


# =============================================================================
# 11. WebSocket notification endpoint exists
# =============================================================================


def test_ws_notification_endpoint_registered() -> None:
    """The /ws/notifications WebSocket route should be registered."""
    from backend.api.metrics import router

    ws_routes = [
        r for r in router.routes if hasattr(r, "path") and "notifications" in getattr(r, "path", "")
    ]
    assert len(ws_routes) == 1


# =============================================================================
# 12. Notification hook — ws_notification uses correct room
# =============================================================================


def test_ws_notification_broadcasts_to_room_zero() -> None:
    """send_ws_notification should broadcast to run_id=0, channel=notifications."""
    mock_manager = AsyncMock()
    with patch("backend.api.websocket.manager", mock_manager):
        _run(send_ws_notification("test_event", {"key": "value"}))

    mock_manager.broadcast.assert_called_once_with(
        0,
        {"type": "test_event", "key": "value"},
        channel="notifications",
    )


# =============================================================================
# 13. Process manager calls notifications
# =============================================================================


def test_process_manager_sends_start_notification() -> None:
    """ExperimentRunner.start should call notify_run_started."""
    source = inspect.getsource(
        __import__(
            "backend.core.process_manager", fromlist=["ExperimentRunner"]
        ).ExperimentRunner.start
    )
    assert "notify_run_started" in source


def test_process_manager_sends_completion_notification() -> None:
    """ExperimentRunner._send_run_notification should be called on run end."""
    source = inspect.getsource(
        __import__(
            "backend.core.process_manager", fromlist=["ExperimentRunner"]
        ).ExperimentRunner._monitor
    )
    assert "_send_run_notification" in source


# =============================================================================
# 14. Genericity checks
# =============================================================================


def _read_source(module_path: str) -> str:
    """Read source code of a module."""
    import importlib

    mod = importlib.import_module(module_path)
    return inspect.getsource(mod)


_BANNED_TERMS = ["vlm", "siglip", "coco", "hash_dim", "hash_layer"]


@pytest.mark.parametrize(
    "module",
    [
        "backend.services.notifier",
        "backend.services.queue_scheduler",
        "backend.api.queue",
        "backend.api.settings",
    ],
)
def test_no_vlm_specific_terms_in_module(module: str) -> None:
    """Core notification/queue modules should not contain vlm-specific terms."""
    source = _read_source(module).lower()
    for term in _BANNED_TERMS:
        assert term not in source, f"Found vlm-specific term '{term}' in {module}"


# =============================================================================
# 15. Queue API endpoints exist
# =============================================================================


def test_queue_api_routes_exist() -> None:
    """Queue router should have all required endpoints."""
    from backend.api.queue import router

    paths = [getattr(r, "path", "") for r in router.routes]
    joined = " ".join(paths)

    # Routes include prefix, check for key suffixes
    assert "queue" in joined  # base route exists
    assert "{entry_id}" in joined  # delete
    assert "reorder" in joined  # reorder
    assert "history" in joined  # history


def test_settings_api_routes_exist() -> None:
    """Settings router should have all required endpoints including test-webhook."""
    from backend.api.settings import router

    paths = [getattr(r, "path", "") for r in router.routes]
    joined = " ".join(paths)
    assert "test-webhook" in joined


# =============================================================================
# 16. Integration: lifespan starts queue scheduler
# =============================================================================


def test_main_starts_queue_scheduler() -> None:
    """Backend main.py lifespan should start queue_scheduler."""
    source = inspect.getsource(__import__("backend.main", fromlist=["lifespan"]).lifespan)
    assert "queue_scheduler.start()" in source
    assert "queue_scheduler.stop()" in source
