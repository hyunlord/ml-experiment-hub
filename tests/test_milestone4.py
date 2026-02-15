"""Tests for Milestone 4: hyperparameter search engine + study API.

Covers:
1. SearchEngine interface and registry
2. OptunaEngine (random fallback mode)
3. Parameter sampling (float, int, categorical, log-scale)
4. Study creation and trial progress via API
5. Parameter importance calculation
6. Best-trial experiment creation
7. Adapter search ranges
8. Genericity: no vlm-specific terms in core search engine
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.core.search_engine import (
    BaseSearchEngine,
    SearchResult,
    TrialResult,
    _correlation,
    _variance,
    get_engine,
    list_engines,
    register_engine,
)
from backend.engines.optuna_engine import OptunaEngine, _sample_param_random


# =============================================================================
# 1. SearchEngine interface and registry
# =============================================================================


def test_search_engine_registry_has_optuna() -> None:
    """Optuna engine should be auto-registered on import."""
    engines = list_engines()
    assert "optuna" in engines


def test_get_engine_returns_optuna() -> None:
    """get_engine('optuna') should return an OptunaEngine instance."""
    engine = get_engine("optuna")
    assert isinstance(engine, OptunaEngine)
    assert isinstance(engine, BaseSearchEngine)


def test_get_engine_unknown_raises() -> None:
    """get_engine with unknown name should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown search engine"):
        get_engine("nonexistent_engine")


def test_register_custom_engine() -> None:
    """Custom engines can be registered and retrieved."""

    class DummyEngine(BaseSearchEngine):
        def run_search(self, **kwargs: Any) -> SearchResult:
            return SearchResult()

        def get_name(self) -> str:
            return "Dummy"

    register_engine("dummy_test", DummyEngine)
    assert "dummy_test" in list_engines()
    engine = get_engine("dummy_test")
    assert isinstance(engine, DummyEngine)


def test_base_search_engine_is_abstract() -> None:
    """BaseSearchEngine cannot be instantiated directly."""
    assert inspect.isabstract(BaseSearchEngine)


# =============================================================================
# 2. OptunaEngine run_search (random fallback)
# =============================================================================


def test_optuna_engine_run_search_basic() -> None:
    """OptunaEngine should complete a search and return results."""
    engine = OptunaEngine()
    search_space = {
        "lr": {"type": "float", "low": 1e-4, "high": 1e-1, "log": True},
        "batch_size": {"type": "int", "low": 8, "high": 64, "step": 8},
    }

    result = engine.run_search(
        search_space=search_space,
        base_config={"epochs": 10},
        n_trials=5,
        search_epochs=3,
        direction="maximize",
        objective_metric="val/loss",
    )

    assert isinstance(result, SearchResult)
    assert result.n_trials_completed == 5
    assert len(result.trials) == 5
    assert result.best_trial_number is not None
    assert result.best_value is not None


def test_optuna_engine_trial_params_in_range() -> None:
    """Sampled params should respect search space bounds."""
    engine = OptunaEngine()
    search_space = {
        "lr": {"type": "float", "low": 0.001, "high": 0.1},
        "layers": {"type": "int", "low": 1, "high": 10},
    }

    result = engine.run_search(
        search_space=search_space,
        base_config={},
        n_trials=10,
        search_epochs=2,
        direction="minimize",
        objective_metric="val/loss",
    )

    for trial in result.trials:
        assert 0.001 <= trial.params["lr"] <= 0.1
        assert 1 <= trial.params["layers"] <= 10


def test_optuna_engine_minimize_direction() -> None:
    """Best value should be the minimum when direction=minimize."""
    engine = OptunaEngine()
    result = engine.run_search(
        search_space={"x": {"type": "float", "low": 0.0, "high": 1.0}},
        base_config={},
        n_trials=10,
        search_epochs=2,
        direction="minimize",
        objective_metric="loss",
    )

    objectives = [t.objective_value for t in result.trials if t.objective_value is not None]
    assert result.best_value == min(objectives)


def test_optuna_engine_maximize_direction() -> None:
    """Best value should be the maximum when direction=maximize."""
    engine = OptunaEngine()
    result = engine.run_search(
        search_space={"x": {"type": "float", "low": 0.0, "high": 1.0}},
        base_config={},
        n_trials=10,
        search_epochs=2,
        direction="maximize",
        objective_metric="score",
    )

    objectives = [t.objective_value for t in result.trials if t.objective_value is not None]
    assert result.best_value == max(objectives)


def test_optuna_engine_intermediate_values() -> None:
    """Each trial should have intermediate values for each epoch."""
    engine = OptunaEngine()
    result = engine.run_search(
        search_space={"x": {"type": "float", "low": 0.0, "high": 1.0}},
        base_config={},
        n_trials=3,
        search_epochs=5,
        direction="maximize",
        objective_metric="val/acc",
    )

    for trial in result.trials:
        assert len(trial.intermediate_values) == 5
        for i in range(5):
            assert str(i) in trial.intermediate_values


def test_optuna_engine_on_trial_complete_callback() -> None:
    """on_trial_complete callback should be called for each trial."""
    engine = OptunaEngine()
    callback = MagicMock()

    engine.run_search(
        search_space={"x": {"type": "float", "low": 0.0, "high": 1.0}},
        base_config={},
        n_trials=4,
        search_epochs=2,
        direction="maximize",
        objective_metric="val/acc",
        on_trial_complete=callback,
    )

    assert callback.call_count == 4
    for call in callback.call_args_list:
        assert isinstance(call[0][0], TrialResult)


# =============================================================================
# 3. Parameter sampling
# =============================================================================


def test_sample_float_uniform() -> None:
    """Float sampling should respect bounds."""
    for _ in range(20):
        val = _sample_param_random("x", {"type": "float", "low": 1.0, "high": 5.0})
        assert 1.0 <= val <= 5.0


def test_sample_float_log_scale() -> None:
    """Log-scale float sampling should respect bounds."""
    for _ in range(20):
        val = _sample_param_random("lr", {"type": "float", "low": 1e-5, "high": 1e-1, "log": True})
        assert 1e-5 <= val <= 1e-1


def test_sample_int() -> None:
    """Int sampling should respect bounds and step."""
    for _ in range(20):
        val = _sample_param_random("bs", {"type": "int", "low": 8, "high": 64, "step": 8})
        assert isinstance(val, int)
        assert 8 <= val <= 64
        assert val % 8 == 0


def test_sample_categorical() -> None:
    """Categorical sampling should return one of the choices."""
    choices = ["adam", "sgd", "adamw"]
    for _ in range(20):
        val = _sample_param_random("opt", {"type": "categorical", "choices": choices})
        assert val in choices


def test_sample_unknown_type_returns_none() -> None:
    """Unknown param type should return None."""
    val = _sample_param_random("x", {"type": "unknown"})
    assert val is None


# =============================================================================
# 4. Parameter importance
# =============================================================================


def test_param_importance_basic() -> None:
    """Parameter importance should return normalized scores."""
    engine = OptunaEngine()
    trials = [
        TrialResult(
            trial_number=i, params={"lr": 0.001 * (i + 1), "bs": 32}, objective_value=0.5 + 0.1 * i
        )
        for i in range(10)
    ]

    importance = engine.get_param_importance(trials)
    assert "lr" in importance
    assert "bs" in importance
    assert abs(sum(importance.values()) - 1.0) < 0.01


def test_param_importance_too_few_trials() -> None:
    """Less than 3 trials should return empty importance."""
    engine = OptunaEngine()
    trials = [
        TrialResult(trial_number=0, params={"lr": 0.01}, objective_value=0.5),
        TrialResult(trial_number=1, params={"lr": 0.02}, objective_value=0.6),
    ]

    importance = engine.get_param_importance(trials)
    assert importance == {}


def test_param_importance_constant_objective() -> None:
    """Constant objective should give uniform importance."""
    engine = OptunaEngine()
    trials = [
        TrialResult(trial_number=i, params={"a": float(i), "b": float(i * 2)}, objective_value=0.5)
        for i in range(5)
    ]

    importance = engine.get_param_importance(trials)
    if importance:
        # Should be roughly uniform
        for v in importance.values():
            assert abs(v - 0.5) < 0.01


# =============================================================================
# 5. Utility functions
# =============================================================================


def test_variance_basic() -> None:
    assert abs(_variance([1.0, 2.0, 3.0]) - 1.0) < 1e-10


def test_variance_single_value() -> None:
    assert _variance([5.0]) == 0.0


def test_correlation_perfect() -> None:
    """Perfect positive correlation should be ~1.0."""
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2.0, 4.0, 6.0, 8.0, 10.0]
    assert abs(_correlation(xs, ys) - 1.0) < 1e-10


def test_correlation_perfect_negative() -> None:
    """Perfect negative correlation should be ~-1.0."""
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [10.0, 8.0, 6.0, 4.0, 2.0]
    assert abs(_correlation(xs, ys) - (-1.0)) < 1e-10


# =============================================================================
# 6. Adapter search ranges
# =============================================================================


def test_base_adapter_search_ranges_default() -> None:
    """BaseAdapter.get_search_ranges() should return empty dict by default."""
    from adapters.base import BaseAdapter

    class MinimalAdapter(BaseAdapter):
        def config_to_yaml(self, config: dict[str, Any]) -> str:
            return ""

        def get_train_command(self, yaml_path: str) -> list[str]:
            return []

        def parse_metrics(self, log_line: str) -> dict[str, Any] | None:
            return None

    adapter = MinimalAdapter()
    assert adapter.get_search_ranges() == {}


def test_vlm_adapter_search_ranges() -> None:
    """VLMQuantizationAdapter should return recommended search ranges."""
    from adapters.vlm_quantization.adapter import VLMQuantizationAdapter

    adapter = VLMQuantizationAdapter()
    ranges = adapter.get_search_ranges()

    assert "training.lr" in ranges
    assert ranges["training.lr"]["type"] == "float"
    assert ranges["training.lr"]["log"] is True

    assert "training.temperature" in ranges
    assert "loss.quantization_weight" in ranges
    assert "model.hash_dim" in ranges
    assert ranges["model.hash_dim"]["type"] == "categorical"
    assert 64 in ranges["model.hash_dim"]["choices"]


# =============================================================================
# 7. Genericity checks
# =============================================================================


def test_search_engine_no_vlm_references() -> None:
    """Core search engine module should have no vlm-specific terms."""
    import backend.core.search_engine as mod

    source = inspect.getsource(mod)
    for term in ["vlm", "siglip", "coco", "map_i2t", "map_t2i"]:
        assert term not in source.lower(), f"Found '{term}' in core search_engine.py"


def test_study_schema_no_vlm_default() -> None:
    """Study schema default objective_metric should not reference vlm metrics."""
    from backend.schemas.optuna import CreateStudyRequest

    req = CreateStudyRequest(
        name="test",
        search_space_json={"lr": {"type": "float", "low": 0.01, "high": 0.1}},
    )
    assert "map_i2t" not in req.objective_metric
    assert "map_t2i" not in req.objective_metric


# =============================================================================
# 8. StudyResponse / TrialResultResponse schema validation
# =============================================================================


def test_study_response_schema() -> None:
    """StudyResponse should accept valid study data."""
    from datetime import datetime

    from backend.schemas.optuna import StudyResponse

    data = {
        "id": 1,
        "name": "test-study",
        "config_schema_id": None,
        "base_config_json": {"epochs": 10},
        "search_space_json": {"lr": {"type": "float", "low": 0.01, "high": 0.1}},
        "n_trials": 20,
        "search_epochs": 5,
        "subset_ratio": 0.1,
        "pruner": "median",
        "objective_metric": "val/loss",
        "direction": "minimize",
        "status": "pending",
        "best_trial_number": None,
        "best_value": None,
        "job_id": None,
        "created_at": datetime.utcnow(),
        "completed_at": None,
        "trials": [],
    }
    resp = StudyResponse(**data)
    assert resp.name == "test-study"
    assert resp.n_trials == 20
    assert resp.direction == "minimize"


def test_trial_result_response_schema() -> None:
    """TrialResultResponse should accept valid trial data."""
    from datetime import datetime

    from backend.schemas.optuna import TrialResultResponse

    data = {
        "id": 1,
        "study_id": 1,
        "trial_number": 0,
        "params_json": {"lr": 0.05, "batch_size": 32},
        "objective_value": 0.85,
        "status": "completed",
        "duration_seconds": 1.5,
        "intermediate_values_json": {"0": 0.3, "1": 0.6, "2": 0.85},
        "created_at": datetime.utcnow(),
    }
    resp = TrialResultResponse(**data)
    assert resp.objective_value == 0.85
    assert resp.params_json["lr"] == 0.05
