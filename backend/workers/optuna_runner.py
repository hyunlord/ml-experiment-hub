"""Optuna search runner subprocess.

Runs an Optuna study with configurable search space.
Reports trial progress back to the hub via HTTP POST.

In dummy mode (no real training), generates random objective values
for E2E testing.

Usage:
    python -m backend.workers.job_runner --config /path/to/config.json
    (with job_type = "optuna_search")
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def report_trial_progress(
    server_url: str,
    study_id: int,
    trial_number: int,
    params_json: dict[str, Any] | None = None,
    objective_value: float | None = None,
    status: str = "running",
    duration_seconds: float | None = None,
    intermediate_values_json: dict[str, Any] | None = None,
) -> None:
    """Report trial progress to the hub."""
    payload: dict[str, Any] = {
        "study_id": study_id,
        "trial_number": trial_number,
        "status": status,
    }
    if params_json:
        payload["params_json"] = params_json
    if objective_value is not None:
        payload["objective_value"] = objective_value
    if duration_seconds is not None:
        payload["duration_seconds"] = duration_seconds
    if intermediate_values_json:
        payload["intermediate_values_json"] = intermediate_values_json

    try:
        resp = httpx.post(
            f"{server_url}/api/studies/{study_id}/trial-progress",
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
    except Exception:
        logger.warning("Failed to report trial %d progress for study %d", trial_number, study_id)


def report_job_progress(
    server_url: str,
    job_id: int,
    progress: int,
    status: str | None = None,
    result_json: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    """Report job progress to the hub."""
    payload: dict[str, Any] = {"job_id": job_id, "progress": progress}
    if status:
        payload["status"] = status
    if result_json:
        payload["result_json"] = result_json
    if error_message:
        payload["error_message"] = error_message

    try:
        resp = httpx.post(
            f"{server_url}/api/jobs/{job_id}/progress",
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
    except Exception:
        logger.warning("Failed to report job %d progress", job_id)


def sample_param(key: str, spec: dict[str, Any]) -> Any:
    """Sample a parameter value from a search space spec (no optuna dependency)."""
    param_type = spec.get("type", "float")

    if param_type == "float":
        low = float(spec.get("low", 0.0))
        high = float(spec.get("high", 1.0))
        if spec.get("log", False):
            import math

            return math.exp(random.uniform(math.log(low), math.log(high)))
        return random.uniform(low, high)

    elif param_type == "int":
        low = int(spec.get("low", 1))
        high = int(spec.get("high", 100))
        step = int(spec.get("step", 1))
        return random.randrange(low, high + 1, step)

    elif param_type == "categorical":
        choices = spec.get("choices", [])
        if not choices:
            return None
        return random.choice(choices)

    return None


def run_optuna_search(
    job_id: int,
    config: dict[str, Any],
    server_url: str,
) -> None:
    """Run an Optuna hyperparameter search.

    Uses dummy mode: generates random objectives without real training.
    This allows full E2E testing of the search pipeline.
    """
    study_id = config["study_id"]
    search_space = config.get("search_space", {})
    n_trials = config.get("n_trials", 20)
    search_epochs = config.get("search_epochs", 5)
    direction = config.get("direction", "maximize")

    logger.info(
        "Starting Optuna search: study=%d, n_trials=%d, epochs=%d",
        study_id,
        n_trials,
        search_epochs,
    )

    report_job_progress(server_url, job_id, 5, status="running")

    best_value: float | None = None
    best_trial: int | None = None

    for trial_num in range(n_trials):
        t0 = time.time()

        # Sample parameters
        params: dict[str, Any] = {}
        for key, spec in search_space.items():
            params[key] = sample_param(key, spec)

        # Report trial start
        report_trial_progress(
            server_url,
            study_id,
            trial_num,
            params_json=params,
            status="running",
        )

        # Simulate training epochs with intermediate values
        intermediate_values: dict[str, float] = {}
        objective = 0.0

        for epoch in range(search_epochs):
            # Dummy objective: influenced by parameter values + noise
            base_score = 0.0
            for key, val in params.items():
                if isinstance(val, (int, float)):
                    # Normalize to [0, 1] range roughly
                    spec = search_space.get(key, {})
                    low = spec.get("low", 0)
                    high = spec.get("high", 1)
                    r = high - low
                    if r > 0:
                        norm = (val - low) / r
                    else:
                        norm = 0.5
                    base_score += norm * 0.3

            # Add epoch-dependent improvement + noise
            progress_factor = (epoch + 1) / search_epochs
            noise = random.gauss(0, 0.05)
            objective = base_score * progress_factor + noise + 0.2 * progress_factor

            intermediate_values[str(epoch)] = round(objective, 6)

            # Small delay to simulate work
            time.sleep(0.05)

        duration = time.time() - t0
        final_value = round(objective, 6)

        # Report trial completion
        report_trial_progress(
            server_url,
            study_id,
            trial_num,
            params_json=params,
            objective_value=final_value,
            status="completed",
            duration_seconds=round(duration, 3),
            intermediate_values_json=intermediate_values,
        )

        # Track best
        if best_value is None or (
            (direction == "maximize" and final_value > best_value)
            or (direction == "minimize" and final_value < best_value)
        ):
            best_value = final_value
            best_trial = trial_num

        # Report job progress
        pct = 5 + int(90 * (trial_num + 1) / n_trials)
        report_job_progress(server_url, job_id, pct)

        logger.info(
            "Trial %d/%d: objective=%.6f, params=%s",
            trial_num + 1,
            n_trials,
            final_value,
            params,
        )

    # Mark study complete
    try:
        httpx.post(f"{server_url}/api/studies/{study_id}/complete", timeout=10.0)
    except Exception:
        logger.warning("Failed to mark study %d complete", study_id)

    # Report job done
    result_json = {
        "best_trial": best_trial,
        "best_value": best_value,
        "n_trials_completed": n_trials,
    }
    report_job_progress(
        server_url,
        job_id,
        100,
        status="completed",
        result_json=result_json,
    )
    logger.info(
        "Optuna search completed: study=%d, best_trial=%s, best_value=%s",
        study_id,
        best_trial,
        best_value,
    )
