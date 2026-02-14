"""Dataset registry service.

Manages dataset definitions (seed + CRUD), file-system status checks,
JSONL preview, and prepare job orchestration.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.config import settings
from backend.models.experiment import DatasetDefinition
from shared.schemas import DatasetStatus, JobStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed data — initial dataset definitions
# ---------------------------------------------------------------------------

SEED_DATASETS: list[dict[str, Any]] = [
    {
        "key": "coco",
        "name": "COCO 2014 (Karpathy Split)",
        "description": "MS-COCO 2014 with Karpathy train/val/test split. Always included as base dataset.",
        "data_root": "coco",
        "raw_path": "coco/dataset_coco.json",
        "jsonl_path": "coco/coco_karpathy.jsonl",
        "raw_format": "coco_karpathy",
    },
    {
        "key": "coco_ko",
        "name": "COCO Korean (AIHub #261)",
        "description": "Korean captions for COCO images (AIHub dataset #261). Reuses COCO image directory.",
        "data_root": "coco",
        "raw_path": "coco_ko/aihub_261_raw.json",
        "jsonl_path": "coco_ko/coco_ko.jsonl",
        "raw_format": "coco_karpathy",
    },
    {
        "key": "aihub",
        "name": "AIHub #71454 (Korean-English)",
        "description": "Korean-English paired image-caption dataset from AIHub (#71454).",
        "data_root": "aihub",
        "raw_path": "aihub/aihub_71454_raw.json",
        "jsonl_path": "aihub/aihub_71454.jsonl",
        "raw_format": "coco_karpathy",
    },
    {
        "key": "cc3m_ko",
        "name": "CC3M-Ko (Bilingual)",
        "description": "CC3M subset with Korean translations. Bilingual captions.",
        "data_root": "cc3m_ko",
        "raw_path": "cc3m_ko/cc3m_ko_raw.json",
        "jsonl_path": "cc3m_ko/cc3m_ko.jsonl",
        "raw_format": "coco_karpathy",
    },
]


async def seed_datasets(session: AsyncSession) -> int:
    """Insert seed datasets if they don't exist yet.

    Returns the number of newly inserted datasets.
    """
    inserted = 0
    for seed in SEED_DATASETS:
        result = await session.execute(
            select(DatasetDefinition).where(DatasetDefinition.key == seed["key"])
        )
        if result.scalar_one_or_none() is None:
            ds = DatasetDefinition(**seed)
            session.add(ds)
            inserted += 1

    if inserted:
        await session.commit()
        logger.info("Seeded %d dataset definitions", inserted)

    return inserted


# ---------------------------------------------------------------------------
# Status checking
# ---------------------------------------------------------------------------


def compute_status(
    ds: DatasetDefinition,
    data_dir: str | None = None,
) -> DatasetStatus:
    """Compute dataset status from file system state.

    Returns:
        READY: JSONL file exists
        RAW_ONLY: Raw data exists but JSONL is missing
        NOT_FOUND: Neither raw nor JSONL found
        PREPARING: A prepare job is currently running
    """
    base = Path(data_dir or settings.DATA_DIR)

    # Check if prepare job is running
    if ds.prepare_job_id is not None:
        return DatasetStatus.PREPARING

    jsonl = base / ds.jsonl_path if ds.jsonl_path else None
    raw = base / ds.raw_path if ds.raw_path else None

    if jsonl and jsonl.exists() and jsonl.stat().st_size > 0:
        return DatasetStatus.READY

    if raw and raw.exists():
        return DatasetStatus.RAW_ONLY

    # Check if data_root exists (images present but no annotations)
    data_root = base / ds.data_root if ds.data_root else None
    if data_root and data_root.exists():
        return DatasetStatus.RAW_ONLY

    return DatasetStatus.NOT_FOUND


def get_file_stats(ds: DatasetDefinition, data_dir: str | None = None) -> dict[str, Any]:
    """Get file size and entry count for a dataset's JSONL."""
    base = Path(data_dir or settings.DATA_DIR)
    jsonl = base / ds.jsonl_path if ds.jsonl_path else None

    if not jsonl or not jsonl.exists():
        return {"entry_count": None, "size_bytes": None}

    size = jsonl.stat().st_size
    count = 0
    try:
        with open(jsonl) as f:
            for line in f:
                if line.strip():
                    count += 1
    except Exception:
        count = 0

    return {"entry_count": count, "size_bytes": size}


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def preview_jsonl(
    ds: DatasetDefinition,
    n: int = 5,
    data_dir: str | None = None,
) -> list[dict[str, Any]]:
    """Read random samples from a dataset's JSONL file.

    Returns up to `n` parsed JSON entries. Each entry typically has:
    - image: relative path to image file
    - caption / caption_ko / caption_en: caption text(s)

    For language detection, a simple heuristic checks for Korean characters.
    """
    base = Path(data_dir or settings.DATA_DIR)
    jsonl = base / ds.jsonl_path if ds.jsonl_path else None

    if not jsonl or not jsonl.exists():
        return []

    # Read all lines (may be large, but for preview this is acceptable)
    lines: list[str] = []
    try:
        with open(jsonl) as f:
            lines = [line for line in f if line.strip()]
    except Exception:
        return []

    if not lines:
        return []

    # Sample random entries
    sample_lines = random.sample(lines, min(n, len(lines)))

    results = []
    for line in sample_lines:
        try:
            entry = json.loads(line)
            # Add language detection for captions
            for cap_key in ("caption", "caption_ko", "caption_en", "text"):
                if cap_key in entry and isinstance(entry[cap_key], str):
                    entry[f"_{cap_key}_lang"] = _detect_language(entry[cap_key])
            # Resolve image path to serve URL
            if "image" in entry:
                img_path = entry["image"]
                # Check if image exists
                full_img = base / ds.data_root / img_path if ds.data_root else base / img_path
                entry["_image_exists"] = full_img.exists()
                entry["_image_url"] = f"/api/datasets/{ds.id}/image?path={img_path}"
            results.append(entry)
        except (json.JSONDecodeError, KeyError):
            continue

    return results


def _detect_language(text: str) -> str:
    """Simple heuristic language detection.

    Checks for Korean (Hangul) characters. Returns 'ko', 'en', or 'mixed'.
    """
    korean_chars = sum(1 for c in text if "\uac00" <= c <= "\ud7a3" or "\u3131" <= c <= "\u3163")
    total_alpha = sum(1 for c in text if c.isalpha())

    if total_alpha == 0:
        return "unknown"

    ratio = korean_chars / total_alpha
    if ratio > 0.5:
        return "ko"
    elif ratio > 0.1:
        return "mixed"
    else:
        return "en"


def language_stats(
    ds: DatasetDefinition,
    sample_size: int = 200,
    data_dir: str | None = None,
) -> dict[str, int]:
    """Get language distribution statistics from JSONL samples.

    Returns counts like {"ko": 80, "en": 100, "mixed": 20}.
    """
    base = Path(data_dir or settings.DATA_DIR)
    jsonl = base / ds.jsonl_path if ds.jsonl_path else None

    if not jsonl or not jsonl.exists():
        return {}

    lines: list[str] = []
    try:
        with open(jsonl) as f:
            lines = [line for line in f if line.strip()]
    except Exception:
        return {}

    if not lines:
        return {}

    sample = random.sample(lines, min(sample_size, len(lines)))
    counts: dict[str, int] = {}

    for line in sample:
        try:
            entry = json.loads(line)
            # Find caption field
            caption = ""
            for key in ("caption", "caption_ko", "caption_en", "text"):
                if key in entry and isinstance(entry[key], str):
                    caption = entry[key]
                    break
            if caption:
                lang = _detect_language(caption)
                counts[lang] = counts.get(lang, 0) + 1
        except (json.JSONDecodeError, KeyError):
            continue

    return counts


# ---------------------------------------------------------------------------
# Prepare job helpers
# ---------------------------------------------------------------------------


async def check_prepare_job_status(
    ds: DatasetDefinition,
    session: AsyncSession,
) -> DatasetStatus:
    """Check if the active prepare job has finished and update accordingly."""
    if ds.prepare_job_id is None:
        return compute_status(ds)

    from backend.models.experiment import Job

    result = await session.execute(select(Job).where(Job.id == ds.prepare_job_id))
    job = result.scalar_one_or_none()

    if not job:
        ds.prepare_job_id = None
        await session.commit()
        return compute_status(ds)

    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        ds.prepare_job_id = None
        # Update cached stats if completed
        if job.status == JobStatus.COMPLETED:
            stats = get_file_stats(ds)
            ds.entry_count = stats["entry_count"]
            ds.size_bytes = stats["size_bytes"]
        await session.commit()
        return compute_status(ds)

    return DatasetStatus.PREPARING
