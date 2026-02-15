"""Optuna-based hyperparameter search engine.

Uses Optuna when available, falls back to random sampling otherwise.
Registers itself as "optuna" in the engine registry on import.
"""

from __future__ import annotations

import logging
import math
import random
import time
from typing import Any

from backend.core.search_engine import (
    BaseSearchEngine,
    SearchResult,
    TrialResult,
    register_engine,
)

logger = logging.getLogger(__name__)

# Try importing optuna — graceful fallback if not installed
try:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False


class OptunaEngine(BaseSearchEngine):
    """Optuna TPE-based hyperparameter search engine.

    Falls back to random sampling when optuna is not installed.
    """

    def get_name(self) -> str:
        if HAS_OPTUNA:
            return "Optuna (TPE)"
        return "Optuna (random fallback — install optuna for TPE)"

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
        """Run hyperparameter search using Optuna or random fallback."""
        if HAS_OPTUNA:
            return self._run_with_optuna(
                search_space=search_space,
                base_config=base_config,
                n_trials=n_trials,
                search_epochs=search_epochs,
                direction=direction,
                objective_metric=objective_metric,
                subset_ratio=subset_ratio,
                pruner=pruner,
                on_trial_complete=on_trial_complete,
            )
        return self._run_random_fallback(
            search_space=search_space,
            base_config=base_config,
            n_trials=n_trials,
            search_epochs=search_epochs,
            direction=direction,
            objective_metric=objective_metric,
            on_trial_complete=on_trial_complete,
        )

    # ------------------------------------------------------------------
    # Optuna-native path
    # ------------------------------------------------------------------

    def _run_with_optuna(
        self,
        search_space: dict[str, dict[str, Any]],
        base_config: dict[str, Any],
        n_trials: int,
        search_epochs: int,
        direction: str,
        objective_metric: str,
        subset_ratio: float,
        pruner: str,
        on_trial_complete: Any | None,
    ) -> SearchResult:
        optuna_direction = (
            optuna.study.StudyDirection.MAXIMIZE
            if direction == "maximize"
            else optuna.study.StudyDirection.MINIMIZE
        )

        optuna_pruner = self._make_pruner(pruner)
        study = optuna.create_study(direction=optuna_direction, pruner=optuna_pruner)

        trials: list[TrialResult] = []
        best_value: float | None = None
        best_trial_num: int | None = None

        for trial_num in range(n_trials):
            trial = study.ask()
            t0 = time.time()

            # Sample params
            params: dict[str, Any] = {}
            for key, spec in search_space.items():
                params[key] = self._suggest_param(trial, key, spec)

            # Dummy objective: simulate training epochs
            intermediate_values: dict[str, float] = {}
            objective = self._dummy_objective(
                params, search_space, search_epochs, intermediate_values
            )

            duration = time.time() - t0

            study.tell(trial, objective)

            result = TrialResult(
                trial_number=trial_num,
                params=params,
                objective_value=round(objective, 6),
                status="completed",
                duration_seconds=round(duration, 3),
                intermediate_values=intermediate_values,
            )
            trials.append(result)

            if best_value is None or (
                (direction == "maximize" and objective > best_value)
                or (direction == "minimize" and objective < best_value)
            ):
                best_value = round(objective, 6)
                best_trial_num = trial_num

            if on_trial_complete:
                on_trial_complete(result)

        return SearchResult(
            best_trial_number=best_trial_num,
            best_value=best_value,
            n_trials_completed=len(trials),
            trials=trials,
        )

    @staticmethod
    def _suggest_param(trial: Any, key: str, spec: dict[str, Any]) -> Any:
        """Use Optuna trial.suggest_* methods."""
        param_type = spec.get("type", "float")
        if param_type == "float":
            return trial.suggest_float(
                key,
                float(spec.get("low", 0.0)),
                float(spec.get("high", 1.0)),
                log=spec.get("log", False),
            )
        elif param_type == "int":
            return trial.suggest_int(
                key,
                int(spec.get("low", 1)),
                int(spec.get("high", 100)),
                step=int(spec.get("step", 1)),
            )
        elif param_type == "categorical":
            choices = spec.get("choices", [])
            if choices:
                return trial.suggest_categorical(key, choices)
        return None

    @staticmethod
    def _make_pruner(pruner_name: str) -> Any:
        if pruner_name == "hyperband":
            return optuna.pruners.HyperbandPruner()
        elif pruner_name == "median":
            return optuna.pruners.MedianPruner()
        return optuna.pruners.NopPruner()

    # ------------------------------------------------------------------
    # Random fallback (no optuna)
    # ------------------------------------------------------------------

    def _run_random_fallback(
        self,
        search_space: dict[str, dict[str, Any]],
        base_config: dict[str, Any],
        n_trials: int,
        search_epochs: int,
        direction: str,
        objective_metric: str,
        on_trial_complete: Any | None,
    ) -> SearchResult:
        trials: list[TrialResult] = []
        best_value: float | None = None
        best_trial_num: int | None = None

        for trial_num in range(n_trials):
            t0 = time.time()

            params: dict[str, Any] = {}
            for key, spec in search_space.items():
                params[key] = _sample_param_random(key, spec)

            intermediate_values: dict[str, float] = {}
            objective = self._dummy_objective(
                params, search_space, search_epochs, intermediate_values
            )

            duration = time.time() - t0

            result = TrialResult(
                trial_number=trial_num,
                params=params,
                objective_value=round(objective, 6),
                status="completed",
                duration_seconds=round(duration, 3),
                intermediate_values=intermediate_values,
            )
            trials.append(result)

            if best_value is None or (
                (direction == "maximize" and objective > best_value)
                or (direction == "minimize" and objective < best_value)
            ):
                best_value = round(objective, 6)
                best_trial_num = trial_num

            if on_trial_complete:
                on_trial_complete(result)

        return SearchResult(
            best_trial_number=best_trial_num,
            best_value=best_value,
            n_trials_completed=len(trials),
            trials=trials,
        )

    # ------------------------------------------------------------------
    # Shared dummy objective (for E2E testing without real training)
    # ------------------------------------------------------------------

    @staticmethod
    def _dummy_objective(
        params: dict[str, Any],
        search_space: dict[str, dict[str, Any]],
        search_epochs: int,
        intermediate_values: dict[str, float],
    ) -> float:
        """Generate a dummy objective influenced by params + noise."""
        base_score = 0.0
        for key, val in params.items():
            if isinstance(val, (int, float)):
                spec = search_space.get(key, {})
                low = spec.get("low", 0)
                high = spec.get("high", 1)
                r = high - low
                norm = (val - low) / r if r > 0 else 0.5
                base_score += norm * 0.3

        objective = 0.0
        for epoch in range(search_epochs):
            progress = (epoch + 1) / search_epochs
            noise = random.gauss(0, 0.05)
            objective = base_score * progress + noise + 0.2 * progress
            intermediate_values[str(epoch)] = round(objective, 6)

        return objective

    # ------------------------------------------------------------------
    # Parameter importance (use Optuna's fANOVA when available)
    # ------------------------------------------------------------------

    def get_param_importance(
        self,
        trials: list[TrialResult],
    ) -> dict[str, float]:
        """Use Optuna importance if available, else fall back to base."""
        if not HAS_OPTUNA or len(trials) < 3:
            return super().get_param_importance(trials)

        try:
            # Reconstruct an Optuna study from our trial data
            study = optuna.create_study(direction="maximize")
            for t in trials:
                if t.objective_value is not None:
                    dist: dict[str, Any] = {}
                    for key, val in t.params.items():
                        if isinstance(val, float):
                            dist[key] = optuna.distributions.FloatDistribution(
                                low=val * 0.5, high=val * 1.5
                            )
                        elif isinstance(val, int):
                            dist[key] = optuna.distributions.IntDistribution(
                                low=max(0, val - 10), high=val + 10
                            )
                    frozen = optuna.trial.create_trial(
                        params=t.params,
                        distributions=dist,
                        values=[t.objective_value],
                    )
                    study.add_trial(frozen)

            importance = optuna.importance.get_param_importances(study)
            return dict(importance)
        except Exception:
            logger.debug("Optuna importance failed, using fallback", exc_info=True)
            return super().get_param_importance(trials)


def _sample_param_random(key: str, spec: dict[str, Any]) -> Any:
    """Sample a parameter value randomly (no optuna dependency)."""
    param_type = spec.get("type", "float")

    if param_type == "float":
        low = float(spec.get("low", 0.0))
        high = float(spec.get("high", 1.0))
        if spec.get("log", False):
            return math.exp(random.uniform(math.log(low), math.log(high)))
        return random.uniform(low, high)
    elif param_type == "int":
        low = int(spec.get("low", 1))
        high = int(spec.get("high", 100))
        step = int(spec.get("step", 1))
        return random.randrange(low, high + 1, step)
    elif param_type == "categorical":
        choices = spec.get("choices", [])
        if choices:
            return random.choice(choices)
    return None


# Self-register on import
register_engine("optuna", OptunaEngine)
