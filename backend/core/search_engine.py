"""Abstract search engine interface for hyperparameter optimization.

The platform core depends only on this interface.
Concrete implementations (Optuna, Ray Tune, etc.) live in backend/engines/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrialResult:
    """Result of a single hyperparameter trial."""

    trial_number: int
    params: dict[str, Any]
    objective_value: float | None = None
    status: str = "completed"
    duration_seconds: float | None = None
    intermediate_values: dict[str, float] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Final result of a hyperparameter search."""

    best_trial_number: int | None = None
    best_value: float | None = None
    n_trials_completed: int = 0
    trials: list[TrialResult] = field(default_factory=list)


class BaseSearchEngine(ABC):
    """Abstract base class for hyperparameter search engines.

    Implementations must provide:
    - run_search(): Execute the full search loop
    - get_name(): Human-readable engine name

    The engine reports progress via a callback so the platform
    can update the DB and UI in real-time.
    """

    @abstractmethod
    def run_search(
        self,
        search_space: dict[str, dict[str, Any]],
        base_config: dict[str, Any],
        n_trials: int,
        search_epochs: int,
        direction: str,
        objective_metric: str,
        *,
        subset_ratio: float = 0.1,
        pruner: str = "median",
        on_trial_complete: Any | None = None,
    ) -> SearchResult:
        """Run the hyperparameter search.

        Args:
            search_space: {param_key: {type, low, high, ...}} definitions.
            base_config: Fixed config values merged with sampled params.
            n_trials: Number of trials to run.
            search_epochs: Training epochs per trial.
            direction: "maximize" or "minimize".
            objective_metric: Metric name to optimize.
            subset_ratio: Fraction of data to use per trial.
            pruner: Pruning strategy name.
            on_trial_complete: Optional callback(TrialResult) for progress.

        Returns:
            SearchResult with all trial outcomes and best config.
        """

    @abstractmethod
    def get_name(self) -> str:
        """Return human-readable engine name."""

    def get_param_importance(
        self,
        trials: list[TrialResult],
    ) -> dict[str, float]:
        """Estimate parameter importance from completed trials.

        Default implementation uses variance-based correlation.
        Engines may override with more sophisticated methods.

        Returns:
            {param_name: importance_score} normalized to sum=1.
        """
        completed = [t for t in trials if t.objective_value is not None]
        if len(completed) < 3:
            return {}

        param_keys = list(completed[0].params.keys())
        objectives = [t.objective_value for t in completed if t.objective_value is not None]

        if not objectives:
            return {}

        obj_var = _variance(objectives)
        if obj_var < 1e-10:
            return {k: 1.0 / len(param_keys) for k in param_keys}

        importances: dict[str, float] = {}
        for key in param_keys:
            values = [t.params.get(key) for t in completed]
            if all(isinstance(v, (int, float)) for v in values):
                corr = abs(
                    _correlation(
                        [float(v) for v in values],  # type: ignore[arg-type]
                        [float(o) for o in objectives],
                    )
                )
                importances[key] = corr
            else:
                importances[key] = 0.0

        total = sum(importances.values()) or 1.0
        return {k: v / total for k, v in importances.items()}


# ------------------------------------------------------------------
# Engine registry
# ------------------------------------------------------------------

_ENGINE_REGISTRY: dict[str, type[BaseSearchEngine]] = {}


def register_engine(name: str, engine_cls: type[BaseSearchEngine]) -> None:
    """Register a search engine implementation."""
    _ENGINE_REGISTRY[name] = engine_cls


def get_engine(name: str) -> BaseSearchEngine:
    """Get an engine instance by name.

    Raises:
        ValueError: If the engine is not registered.
    """
    if name not in _ENGINE_REGISTRY:
        available = ", ".join(_ENGINE_REGISTRY.keys()) or "(none)"
        raise ValueError(f"Unknown search engine '{name}'. Available: {available}")
    return _ENGINE_REGISTRY[name]()


def list_engines() -> list[str]:
    """Return registered engine names."""
    return list(_ENGINE_REGISTRY.keys())


# ------------------------------------------------------------------
# Utility helpers (shared by default implementations)
# ------------------------------------------------------------------


def _variance(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / (n - 1)


def _correlation(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov: float = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - 1)
    sx: float = _variance(xs) ** 0.5
    sy: float = _variance(ys) ** 0.5
    if sx < 1e-10 or sy < 1e-10:
        return 0.0
    return cov / (sx * sy)
