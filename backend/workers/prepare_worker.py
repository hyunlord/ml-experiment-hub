"""Dataset JSONL preparation worker.

Runs as a subprocess to convert raw annotations into JSONL format.
Reports progress via HTTP callbacks to the hub server.

Supported raw formats:
- coco_karpathy: COCO-style JSON with Karpathy split annotations
- jsonl_copy: Raw data is already JSONL, just copy/validate

Usage:
    python -m backend.workers.prepare_worker --config /path/to/config.json

Config JSON:
    {
        "job_id": 1,
        "dataset_id": 1,
        "data_dir": "./data",
        "data_root": "coco",
        "raw_path": "coco/dataset_coco.json",
        "jsonl_path": "coco/coco_karpathy.jsonl",
        "raw_format": "coco_karpathy",
        "server_url": "http://localhost:8002"
    }
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def report_progress(server_url: str, job_id: int, progress: int, **kwargs: object) -> None:
    """Report progress to the hub server."""
    try:
        httpx.post(
            f"{server_url}/api/jobs/{job_id}/progress",
            json={"progress": progress, **kwargs},
            timeout=5.0,
        )
    except Exception:
        logger.warning("Failed to report progress %d%%", progress)


def prepare_coco_karpathy(
    raw_path: Path,
    jsonl_path: Path,
    data_root: str,
    server_url: str,
    job_id: int,
) -> int:
    """Convert COCO Karpathy JSON to JSONL format.

    Expected raw JSON structure:
    {
        "images": [
            {
                "filename": "COCO_val2014_000000391895.jpg",
                "filepath": "val2014",
                "sentids": [0, 1, ...],
                "sentences": [
                    {"raw": "A man with a ...", "tokens": [...]}
                ],
                "split": "train"
            }
        ]
    }

    Or simpler format:
    {
        "annotations": [
            {"image_id": 1, "caption": "text..."},
            ...
        ],
        "images": [
            {"id": 1, "file_name": "image.jpg"},
            ...
        ]
    }

    Output JSONL format (one per line):
    {"image": "val2014/COCO_val2014_000000391895.jpg", "caption": "A man with a ..."}
    """
    logger.info("Reading raw annotations: %s", raw_path)
    report_progress(server_url, job_id, 5)

    with open(raw_path) as f:
        raw = json.load(f)

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    entries_written = 0

    # Detect format
    if "images" in raw and isinstance(raw["images"], list):
        images = raw["images"]
        total = len(images)

        # Check if it's Karpathy format (sentences in images)
        if total > 0 and "sentences" in images[0]:
            logger.info("Detected Karpathy format with %d images", total)
            report_progress(server_url, job_id, 10)

            with open(jsonl_path, "w") as out:
                for i, img in enumerate(images):
                    filepath = img.get("filepath", "")
                    filename = img.get("filename", img.get("file_name", ""))
                    if filepath:
                        image_path = f"{filepath}/{filename}"
                    else:
                        image_path = filename

                    sentences = img.get("sentences", [])
                    for sent in sentences:
                        caption = sent.get("raw", sent.get("caption", ""))
                        if caption and image_path:
                            entry = {"image": image_path, "caption": caption}
                            # Include split info if available
                            if "split" in img:
                                entry["split"] = img["split"]
                            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                            entries_written += 1

                    if i % max(1, total // 20) == 0:
                        pct = 10 + int(80 * (i + 1) / total)
                        report_progress(server_url, job_id, min(pct, 90))

        # Standard COCO format (separate annotations)
        elif "annotations" in raw:
            annotations = raw["annotations"]
            total_ann = len(annotations)
            logger.info(
                "Detected COCO format with %d images, %d annotations",
                total,
                total_ann,
            )
            report_progress(server_url, job_id, 10)

            # Build image ID → filename mapping
            id_to_file: dict[int, str] = {}
            for img in images:
                img_id = img.get("id", img.get("image_id"))
                fname = img.get("file_name", img.get("filename", ""))
                if img_id is not None and fname:
                    id_to_file[img_id] = fname

            with open(jsonl_path, "w") as out:
                for i, ann in enumerate(annotations):
                    image_id = ann.get("image_id")
                    caption = ann.get("caption", "")
                    fname = id_to_file.get(image_id, "")
                    if caption and fname:
                        entry = {"image": fname, "caption": caption}
                        out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        entries_written += 1

                    if i % max(1, total_ann // 20) == 0:
                        pct = 10 + int(80 * (i + 1) / total_ann)
                        report_progress(server_url, job_id, min(pct, 90))
        else:
            # Simple list of image dicts with caption field
            logger.info("Detected simple image list format with %d entries", total)
            report_progress(server_url, job_id, 10)

            with open(jsonl_path, "w") as out:
                for i, img in enumerate(images):
                    caption = img.get("caption", img.get("text", ""))
                    image_path = img.get("image", img.get("file_name", img.get("filename", "")))
                    if caption and image_path:
                        entry = {"image": image_path, "caption": caption}
                        out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        entries_written += 1

                    if i % max(1, total // 20) == 0:
                        pct = 10 + int(80 * (i + 1) / total)
                        report_progress(server_url, job_id, min(pct, 90))
    else:
        raise ValueError(f"Unrecognized raw format in {raw_path}")

    report_progress(server_url, job_id, 95)
    logger.info("Wrote %d entries to %s", entries_written, jsonl_path)
    return entries_written


def prepare_jsonl_copy(
    raw_path: Path,
    jsonl_path: Path,
    server_url: str,
    job_id: int,
) -> int:
    """Copy and validate an existing JSONL file.

    Reads each line, validates JSON, and writes to output path.
    """
    logger.info("Validating and copying JSONL: %s -> %s", raw_path, jsonl_path)
    report_progress(server_url, job_id, 10)

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    entries_written = 0
    total_lines = sum(1 for _ in open(raw_path))

    with open(raw_path) as inp, open(jsonl_path, "w") as out:
        for i, line in enumerate(inp):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                entries_written += 1
            except json.JSONDecodeError:
                logger.warning("Skipping invalid JSON at line %d", i + 1)

            if i % max(1, total_lines // 20) == 0:
                pct = 10 + int(80 * (i + 1) / total_lines)
                report_progress(server_url, job_id, min(pct, 90))

    report_progress(server_url, job_id, 95)
    logger.info("Copied %d valid entries to %s", entries_written, jsonl_path)
    return entries_written


def main() -> int:
    """Main entry point for prepare worker."""
    parser = argparse.ArgumentParser(description="Dataset JSONL preparation worker")
    parser.add_argument("--config", required=True, help="Path to config JSON file")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    job_id = config["job_id"]
    data_dir = config.get("data_dir", "./data")
    raw_path = Path(data_dir) / config["raw_path"]
    jsonl_path = Path(data_dir) / config["jsonl_path"]
    raw_format = config.get("raw_format", "coco_karpathy")
    server_url = config.get("server_url", "http://localhost:8002")

    logger.info(
        "Starting prepare job %d: format=%s, raw=%s, out=%s",
        job_id,
        raw_format,
        raw_path,
        jsonl_path,
    )

    try:
        report_progress(server_url, job_id, 0, status="running")

        if not raw_path.exists():
            raise FileNotFoundError(f"Raw file not found: {raw_path}")

        if raw_format == "coco_karpathy":
            count = prepare_coco_karpathy(
                raw_path, jsonl_path, config.get("data_root", ""), server_url, job_id
            )
        elif raw_format == "jsonl_copy":
            count = prepare_jsonl_copy(raw_path, jsonl_path, server_url, job_id)
        else:
            raise ValueError(f"Unsupported raw format: {raw_format}")

        # Report completion
        report_progress(
            server_url,
            job_id,
            100,
            status="completed",
            result_json={"entry_count": count, "jsonl_path": str(jsonl_path)},
        )

        logger.info("Prepare job %d completed: %d entries", job_id, count)
        return 0

    except Exception as e:
        logger.exception("Prepare job %d failed", job_id)
        report_progress(
            server_url,
            job_id,
            0,
            status="failed",
            error_message=str(e),
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
