"""Dataset availability API for checking training data status."""

import logging
from pathlib import Path

from fastapi import APIRouter

from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

# Registry mapping UI dataset keys → expected file paths relative to DATA_DIR.
DATASET_REGISTRY: dict[str, dict[str, str]] = {
    "coco": {
        "jsonl_path": "",  # validated via karpathy_json or image dirs
        "check_path": "coco/dataset_coco.json",
        "label": "COCO 2014 (Karpathy Split)",
    },
    "coco_ko": {
        "check_path": "coco_ko/coco_ko.jsonl",
        "label": "COCO Korean (AIHub #261)",
    },
    "aihub": {
        "check_path": "aihub/aihub_71454.jsonl",
        "label": "AIHub #71454 (Korean-English)",
    },
    "cc3m_ko": {
        "check_path": "cc3m_ko/cc3m_ko.jsonl",
        "label": "CC3M-Ko (Bilingual)",
    },
}


def _count_jsonl_lines(path: Path) -> int:
    """Count non-empty lines in a JSONL file."""
    try:
        with open(path) as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


@router.get("/status")
async def dataset_status() -> dict[str, dict[str, str | int | bool | None]]:
    """Check availability and entry count of each registered dataset.

    Returns:
        Dict mapping dataset key to {available, entries, expected_path, label}.
    """
    data_dir = Path(settings.DATA_DIR)
    result = {}

    for key, info in DATASET_REGISTRY.items():
        check_path = data_dir / info["check_path"]
        available = check_path.exists()
        entries = _count_jsonl_lines(check_path) if available and check_path.suffix == ".jsonl" else None

        result[key] = {
            "available": available,
            "entries": entries,
            "expected_path": str(info["check_path"]),
            "label": info["label"],
        }

    return result
