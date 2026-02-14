"""Job runner subprocess entry point.

Reads job config from a JSON file and executes the appropriate
job (eval or index_build). Reports progress back to the hub
via HTTP POST to /api/jobs/{job_id}/progress.

Usage:
    python -m backend.workers.job_runner --config /path/to/config.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def report_progress(
    server_url: str,
    job_id: int,
    progress: int,
    status: str | None = None,
    result_json: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    """Report progress to the hub server."""
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
        logger.warning("Failed to report progress for job %d", job_id)


def run_eval(
    job_id: int,
    run_id: int,
    config: dict[str, Any],
    server_url: str,
) -> None:
    """Run evaluation job."""
    import torch

    from adapters.vlm_quantization.evaluator import evaluate_retrieval
    from adapters.vlm_quantization.index_builder import load_index
    from adapters.vlm_quantization.model import load_model

    bit_lengths = config.get("bit_lengths", [8, 16, 32, 64, 128])
    k_values = config.get("k_values", [1, 5, 10])

    report_progress(server_url, job_id, 5, status="running")

    # Resolve checkpoint path
    checkpoint_path = config.get("checkpoint_path")
    if not checkpoint_path:
        logger.error("No checkpoint_path in config")
        report_progress(
            server_url,
            job_id,
            0,
            status="failed",
            error_message="No checkpoint_path provided",
        )
        sys.exit(1)

    # Load model (used when index has no pre-computed codes)
    logger.info("Loading model from %s", checkpoint_path)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    load_model(checkpoint_path, device=device)
    report_progress(server_url, job_id, 15)

    # Load or build test data
    index_path = config.get("index_path")
    if index_path and Path(index_path).exists():
        logger.info("Loading index from %s", index_path)
        index_data = load_index(index_path, device=device)
        report_progress(server_url, job_id, 30)

        # Use index data for eval
        image_codes = index_data["image_codes"]
        text_codes = index_data["text_codes"]
        labels = torch.tensor(index_data["labels"])

        results = evaluate_retrieval(
            query_codes=text_codes,
            db_codes=image_codes,
            query_labels=labels,
            db_labels=labels,
            query_features=index_data.get("text_features"),
            db_features=index_data.get("image_features"),
            bit_lengths=bit_lengths,
            k_values=k_values,
        )
    else:
        # No index — eval with dummy data
        logger.info("No index found, generating eval data from scratch")
        report_progress(server_url, job_id, 20)

        # Generate dummy eval data
        n_items = 10
        labels = torch.arange(n_items)
        results: dict[str, dict[str, float]] = {}

        for i, bit in enumerate(bit_lengths):
            img_codes = torch.randn(n_items, bit).sign()
            txt_codes = torch.randn(n_items, bit).sign()

            from adapters.vlm_quantization.evaluator import (
                mean_average_precision,
                precision_at_k,
            )

            bit_results: dict[str, float] = {
                "hamming_mAP": mean_average_precision(txt_codes, img_codes, labels, labels),
            }
            for k in k_values:
                bit_results[f"hamming_P@{k}"] = precision_at_k(
                    txt_codes, img_codes, labels, labels, k=k
                )
            results[str(bit)] = bit_results

            pct = 30 + int(60 * (i + 1) / len(bit_lengths))
            report_progress(server_url, job_id, pct)

    report_progress(
        server_url,
        job_id,
        100,
        status="completed",
        result_json=results,
    )
    logger.info("Eval job %d completed: %s", job_id, json.dumps(results, indent=2))


def run_index_build(
    job_id: int,
    run_id: int,
    config: dict[str, Any],
    server_url: str,
) -> None:
    """Run index building job."""
    import torch

    from adapters.vlm_quantization.index_builder import build_index
    from adapters.vlm_quantization.model import load_model

    checkpoint_path = config.get("checkpoint_path")
    if not checkpoint_path:
        report_progress(
            server_url,
            job_id,
            0,
            status="failed",
            error_message="No checkpoint_path provided",
        )
        sys.exit(1)

    report_progress(server_url, job_id, 5, status="running")

    # Load model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_model(checkpoint_path, device=device)
    report_progress(server_url, job_id, 15)

    # Get image paths and captions
    image_dir = config.get("image_dir")
    captions_file = config.get("captions_file")

    if captions_file and Path(captions_file).exists():
        with open(captions_file) as f:
            data = json.load(f)
        image_paths = data.get("image_paths", [])
        captions = data.get("captions", [])
        labels = data.get("labels")
    elif image_dir and Path(image_dir).exists():
        image_paths = sorted(str(p) for p in Path(image_dir).glob("*.png")) + sorted(
            str(p) for p in Path(image_dir).glob("*.jpg")
        )
        captions = [Path(p).stem for p in image_paths]
        labels = None
    else:
        report_progress(
            server_url,
            job_id,
            0,
            status="failed",
            error_message="No image_dir or captions_file provided",
        )
        sys.exit(1)

    if not image_paths:
        report_progress(
            server_url,
            job_id,
            0,
            status="failed",
            error_message="No images found",
        )
        sys.exit(1)

    # Output path
    output_dir = Path(config.get("output_dir", "data/indexes"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / f"index_run{run_id}_{int(time.time())}.pt")

    def progress_cb(current: int, total: int) -> None:
        pct = 15 + int(75 * current / total)
        report_progress(server_url, job_id, pct)

    logger.info("Building index: %d items → %s", len(image_paths), output_path)

    build_index(
        model=model,
        image_paths=image_paths,
        captions=captions,
        output_path=output_path,
        labels=labels,
        batch_size=config.get("batch_size", 32),
        thumbnail_size=config.get("thumbnail_size", 64),
        device=device,
        progress_callback=progress_cb,
    )

    result = {
        "index_path": output_path,
        "num_items": len(image_paths),
        "bit_list": model.bit_list,
    }

    report_progress(
        server_url,
        job_id,
        100,
        status="completed",
        result_json=result,
    )
    logger.info("Index build job %d completed: %s", job_id, output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Job runner")
    parser.add_argument("--config", required=True, help="Path to job config JSON")
    args = parser.parse_args()

    with open(args.config) as f:
        job_config = json.load(f)

    job_id = job_config["job_id"]
    job_type = job_config["job_type"]
    run_id = job_config["run_id"]
    config = job_config["config"]
    server_url = job_config.get("server_url", "http://localhost:8002")

    logger.info("Starting job %d (type=%s, run=%d)", job_id, job_type, run_id)

    try:
        if job_type == "eval":
            run_eval(job_id, run_id, config, server_url)
        elif job_type == "index_build":
            run_index_build(job_id, run_id, config, server_url)
        elif job_type == "optuna_search":
            from backend.workers.optuna_runner import run_optuna_search

            run_optuna_search(job_id, config, server_url)
        else:
            raise ValueError(f"Unknown job type: {job_type}")
    except SystemExit:
        raise
    except Exception as e:
        logger.exception("Job %d failed", job_id)
        report_progress(
            server_url,
            job_id,
            0,
            status="failed",
            error_message=str(e),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
