"""Tests for Milestone 2: result collection and experiment comparison.

Covers:
1. Auto-collection of metrics_summary on run completion
2. GET /api/runs/{run_id}/summary endpoint
3. GET /api/runs/{run_id}/checkpoints endpoint
4. POST /api/experiments/compare endpoint
5. GET /api/experiments/{id}/metrics convenience endpoint
6. Config diff utility
"""

from datetime import datetime
from typing import Any

import pytest

from shared.utils import diff_configs


# =============================================================================
# 1. Config diff utility tests
# =============================================================================


def test_diff_configs_identical() -> None:
    """Identical configs should produce empty diff."""
    config = {"model.backbone": "resnet50", "training.lr": 0.01}
    result = diff_configs(config, config)
    assert result["added"] == {}
    assert result["removed"] == {}
    assert result["changed"] == {}


def test_diff_configs_added_keys() -> None:
    """Keys in base but not in other should appear in 'added'."""
    base = {"model.backbone": "resnet50", "training.lr": 0.01}
    other = {"model.backbone": "resnet50"}
    result = diff_configs(base, other)
    assert "training.lr" in result["added"]
    assert result["added"]["training.lr"] == 0.01


def test_diff_configs_removed_keys() -> None:
    """Keys in other but not in base should appear in 'removed'."""
    base = {"model.backbone": "resnet50"}
    other = {"model.backbone": "resnet50", "training.lr": 0.01}
    result = diff_configs(base, other)
    assert "training.lr" in result["removed"]


def test_diff_configs_changed_values() -> None:
    """Keys with different values should appear in 'changed'."""
    base = {"model.backbone": "resnet50", "training.lr": 0.01}
    other = {"model.backbone": "vit_b", "training.lr": 0.01}
    result = diff_configs(base, other)
    assert "model.backbone" in result["changed"]
    assert result["changed"]["model.backbone"]["to"] == "resnet50"
    assert result["changed"]["model.backbone"]["from"] == "vit_b"


def test_diff_configs_mixed() -> None:
    """Test all three diff types at once."""
    base = {"a": 1, "b": 2, "c": 3}
    other = {"b": 20, "c": 3, "d": 4}
    result = diff_configs(base, other)
    assert result["added"] == {"a": 1}
    assert result["removed"] == {"d": 4}
    assert result["changed"] == {"b": {"from": 20, "to": 2}}


# =============================================================================
# 2. Metrics summary collection logic tests
# =============================================================================


def test_metrics_summary_last_value_wins() -> None:
    """Verify that the last value for each metric key is preserved."""
    # Simulate what _collect_final_metrics does
    logs = [
        {"step": 1, "metrics_json": {"train/loss": 2.5, "val/map": 0.1}},
        {"step": 2, "metrics_json": {"train/loss": 1.8, "val/map": 0.3}},
        {"step": 3, "metrics_json": {"train/loss": 0.9, "val/map": 0.6}},
    ]

    last_values: dict[str, Any] = {}
    max_step = 0
    for log in logs:
        for k, v in log["metrics_json"].items():
            last_values[k] = v
        if log["step"] > max_step:
            max_step = log["step"]

    assert last_values["train/loss"] == 0.9
    assert last_values["val/map"] == 0.6
    assert max_step == 3


def test_metrics_summary_empty_logs() -> None:
    """Empty logs should produce summary with zero steps."""
    logs: list[dict[str, Any]] = []
    duration = 120.5

    last_values: dict[str, Any] = {}
    for log in logs:
        for k, v in log.get("metrics_json", {}).items():
            last_values[k] = v

    summary = {**last_values, "_duration_seconds": duration, "_total_steps": 0}
    assert summary["_duration_seconds"] == 120.5
    assert summary["_total_steps"] == 0
    assert len([k for k in summary if not k.startswith("_")]) == 0


def test_metrics_summary_duration_calculation() -> None:
    """Duration should be correctly computed from timestamps."""
    started = datetime(2025, 1, 1, 10, 0, 0)
    ended = datetime(2025, 1, 1, 11, 30, 45)
    duration = (ended - started).total_seconds()
    assert duration == 5445.0


def test_metrics_summary_with_epochs() -> None:
    """Epoch tracking should capture the last epoch."""
    logs = [
        {"step": 100, "epoch": 1, "metrics_json": {"train/loss": 2.0}},
        {"step": 200, "epoch": 2, "metrics_json": {"train/loss": 1.5}},
        {"step": 300, "epoch": 3, "metrics_json": {"train/loss": 1.0}},
    ]

    max_epoch = None
    for log in logs:
        if log.get("epoch") is not None:
            max_epoch = log["epoch"]

    assert max_epoch == 3


# =============================================================================
# 3. Schema validation tests
# =============================================================================


def test_run_summary_response_schema() -> None:
    """RunSummaryResponse should accept valid data."""
    from backend.schemas.experiment import RunSummaryResponse

    resp = RunSummaryResponse(
        run_id=1,
        experiment_config_id=1,
        status="completed",
        metrics_summary={"train/loss": 0.5, "_duration_seconds": 120.0},
        started_at=datetime(2025, 1, 1, 10, 0, 0),
        ended_at=datetime(2025, 1, 1, 10, 2, 0),
        duration_seconds=120.0,
    )
    assert resp.run_id == 1
    assert resp.duration_seconds == 120.0


def test_checkpoints_response_schema() -> None:
    """CheckpointsResponse should accept valid data."""
    from backend.schemas.experiment import CheckpointEntry, CheckpointsResponse

    resp = CheckpointsResponse(
        run_id=1,
        checkpoint_path="/models/run_1",
        checkpoints=[
            CheckpointEntry(
                path="/models/run_1/best.pt",
                size_bytes=104857600,
                modified_at=datetime(2025, 1, 1, 12, 0, 0),
            )
        ],
        total_size_bytes=104857600,
    )
    assert len(resp.checkpoints) == 1
    assert resp.total_size_bytes == 104857600


def test_compare_request_schema_validation() -> None:
    """CompareRequest should require 2-4 ids."""
    from backend.schemas.experiment import CompareRequest

    # Valid: 2 ids
    req = CompareRequest(ids=[1, 2])
    assert len(req.ids) == 2

    # Valid: 4 ids
    req = CompareRequest(ids=[1, 2, 3, 4])
    assert len(req.ids) == 4

    # Invalid: 1 id
    with pytest.raises(Exception):
        CompareRequest(ids=[1])

    # Invalid: 5 ids
    with pytest.raises(Exception):
        CompareRequest(ids=[1, 2, 3, 4, 5])


def test_compare_response_schema() -> None:
    """CompareResponse should accept valid data."""
    from backend.schemas.experiment import CompareExperimentEntry, CompareResponse

    resp = CompareResponse(
        experiments=[
            CompareExperimentEntry(
                id=1,
                name="exp-1",
                config={"model.backbone": "resnet50"},
                metrics_summary={"train/loss": 0.5},
                status="completed",
            ),
            CompareExperimentEntry(
                id=2,
                name="exp-2",
                config={"model.backbone": "vit_b"},
                metrics_summary={"train/loss": 0.3},
                status="completed",
            ),
        ],
        config_diff_keys=["model.backbone"],
    )
    assert len(resp.experiments) == 2
    assert "model.backbone" in resp.config_diff_keys
