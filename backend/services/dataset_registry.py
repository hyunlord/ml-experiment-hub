"""Dataset registry service.

Manages dataset definitions (seed + CRUD), file-system status checks,
JSONL preview, split computation, auto-detect, and prepare job orchestration.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import random
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.config import settings
from backend.models.experiment import DatasetDefinition
from shared.schemas import (
    DatasetFormat,
    DatasetStatus,
    DatasetType,
    JobStatus,
    SplitMethod,
)

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
        "dataset_type": DatasetType.IMAGE_TEXT,
        "dataset_format": DatasetFormat.JSONL,
        "split_method": SplitMethod.FIELD,
        "splits_config": {"field": "split"},
        "is_seed": True,
    },
    {
        "key": "coco_ko",
        "name": "COCO Korean (AIHub #261)",
        "description": "Korean captions for COCO images (AIHub dataset #261). Reuses COCO image directory.",
        "data_root": "coco",
        "raw_path": "coco_ko/aihub_261_raw.json",
        "jsonl_path": "coco_ko/coco_ko.jsonl",
        "raw_format": "coco_karpathy",
        "dataset_type": DatasetType.IMAGE_TEXT,
        "dataset_format": DatasetFormat.JSONL,
        "split_method": SplitMethod.FIELD,
        "splits_config": {"field": "split"},
        "is_seed": True,
    },
    {
        "key": "aihub",
        "name": "AIHub #71454 (Korean-English)",
        "description": "Korean-English paired image-caption dataset from AIHub (#71454).",
        "data_root": "aihub",
        "raw_path": "aihub/aihub_71454_raw.json",
        "jsonl_path": "aihub/aihub_71454.jsonl",
        "raw_format": "coco_karpathy",
        "dataset_type": DatasetType.IMAGE_TEXT,
        "dataset_format": DatasetFormat.JSONL,
        "split_method": SplitMethod.FIELD,
        "splits_config": {"field": "split"},
        "is_seed": True,
    },
    {
        "key": "cc3m_ko",
        "name": "CC3M-Ko (Bilingual)",
        "description": "CC3M subset with Korean translations. Bilingual captions.",
        "data_root": "cc3m_ko",
        "raw_path": "cc3m_ko/cc3m_ko_raw.json",
        "jsonl_path": "cc3m_ko/cc3m_ko.jsonl",
        "raw_format": "coco_karpathy",
        "dataset_type": DatasetType.IMAGE_TEXT,
        "dataset_format": DatasetFormat.JSONL,
        "split_method": SplitMethod.FIELD,
        "splits_config": {"field": "split"},
        "is_seed": True,
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
# Auto-detect
# ---------------------------------------------------------------------------


def detect_dataset(path: str, data_dir: str | None = None) -> dict[str, Any]:
    """Detect format, type, and entry count from a file or directory path.

    Returns:
        {format, type, entry_count, raw_format, error?}
    """
    base = Path(data_dir or settings.DATA_DIR)
    target = base / path if not Path(path).is_absolute() else Path(path)

    result: dict[str, Any] = {
        "format": None,
        "type": None,
        "entry_count": None,
        "raw_format": None,
        "exists": False,
    }

    if not target.exists():
        result["error"] = "Path not found"
        return result

    result["exists"] = True

    if target.is_dir():
        return _detect_directory(target, result)

    suffix = target.suffix.lower()
    if suffix == ".jsonl":
        return _detect_jsonl(target, result)
    elif suffix == ".json":
        return _detect_json(target, result)
    elif suffix == ".csv":
        return _detect_csv(target, result)
    elif suffix == ".parquet":
        result["format"] = DatasetFormat.PARQUET.value
        result["type"] = DatasetType.TABULAR.value
        result["raw_format"] = "parquet"
        return result
    else:
        result["format"] = DatasetFormat.JSONL.value
        result["type"] = DatasetType.CUSTOM.value
        result["raw_format"] = "custom"
        return result


def _detect_directory(target: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Detect a directory dataset (image folder, etc.)."""
    result["format"] = DatasetFormat.DIRECTORY.value
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
    images = [f for f in target.rglob("*") if f.suffix.lower() in image_exts]
    if images:
        result["type"] = DatasetType.IMAGE_ONLY.value
        result["entry_count"] = len(images)
    else:
        result["type"] = DatasetType.CUSTOM.value
        result["entry_count"] = sum(1 for _ in target.rglob("*") if _.is_file())
    result["raw_format"] = "directory"
    return result


def _detect_jsonl(target: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Detect a JSONL file."""
    result["format"] = DatasetFormat.JSONL.value
    result["raw_format"] = "jsonl_copy"
    count = 0
    has_image = False
    has_caption = False
    has_text = False
    try:
        with open(target) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                count += 1
                if i < 5:
                    try:
                        entry = json.loads(line)
                        if "image" in entry:
                            has_image = True
                        if "caption" in entry or "caption_ko" in entry:
                            has_caption = True
                        if "text" in entry:
                            has_text = True
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass

    result["entry_count"] = count
    if has_image and (has_caption or has_text):
        result["type"] = DatasetType.IMAGE_TEXT.value
    elif has_image:
        result["type"] = DatasetType.IMAGE_ONLY.value
    elif has_text or has_caption:
        result["type"] = DatasetType.TEXT_ONLY.value
    else:
        result["type"] = DatasetType.CUSTOM.value
    return result


def _detect_json(target: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Detect a JSON file (COCO format, etc.)."""
    result["format"] = DatasetFormat.JSONL.value  # will be converted to JSONL
    result["raw_format"] = "coco_karpathy"
    try:
        with open(target) as f:
            data = json.load(f)
        if isinstance(data, dict) and "images" in data:
            images = data["images"]
            result["entry_count"] = len(images)
            if images and "sentences" in images[0]:
                # Karpathy format
                total_sents = sum(len(img.get("sentences", [])) for img in images)
                result["entry_count"] = total_sents
            elif "annotations" in data:
                result["entry_count"] = len(data["annotations"])
            result["type"] = DatasetType.IMAGE_TEXT.value
        elif isinstance(data, list):
            result["entry_count"] = len(data)
            result["type"] = DatasetType.CUSTOM.value
        else:
            result["type"] = DatasetType.CUSTOM.value
    except Exception:
        result["type"] = DatasetType.CUSTOM.value
    return result


def _detect_csv(target: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Detect a CSV file."""
    result["format"] = DatasetFormat.CSV.value
    result["raw_format"] = "csv"
    count = 0
    has_image = False
    has_text = False
    try:
        with open(target, newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                header_lower = [h.lower() for h in header]
                has_image = any(h in header_lower for h in ("image", "image_path", "file"))
                has_text = any(
                    h in header_lower for h in ("text", "caption", "label", "description")
                )
                for _ in reader:
                    count += 1
    except Exception:
        pass

    result["entry_count"] = count
    if has_image and has_text:
        result["type"] = DatasetType.IMAGE_TEXT.value
    elif has_image:
        result["type"] = DatasetType.IMAGE_ONLY.value
    elif has_text:
        result["type"] = DatasetType.TEXT_ONLY.value
    else:
        result["type"] = DatasetType.TABULAR.value
    return result


# ---------------------------------------------------------------------------
# Split computation
# ---------------------------------------------------------------------------


def compute_split_preview(
    ds: DatasetDefinition,
    split_method: str | None = None,
    splits_config: dict[str, Any] | None = None,
    data_dir: str | None = None,
) -> dict[str, int]:
    """Compute how many entries each split would contain.

    Returns: {"train": 1000, "val": 100, "test": 100}
    """
    method = SplitMethod(split_method) if split_method else ds.split_method
    config = splits_config if splits_config is not None else ds.splits_config
    base = Path(data_dir or settings.DATA_DIR)
    jsonl = base / ds.jsonl_path if ds.jsonl_path else None

    if method == SplitMethod.NONE:
        total = _count_jsonl_lines(jsonl)
        return {"all": total} if total else {}

    if method == SplitMethod.RATIO:
        total = _count_jsonl_lines(jsonl)
        if not total:
            return {}
        ratios = config.get("ratios", {"train": 0.8, "val": 0.1, "test": 0.1})
        result: dict[str, int] = {}
        remaining = total
        for i, (name, ratio) in enumerate(ratios.items()):
            if i == len(ratios) - 1:
                result[name] = remaining
            else:
                count = int(math.floor(total * float(ratio)))
                result[name] = count
                remaining -= count
        return result

    if method == SplitMethod.FIELD:
        field_name = config.get("field", "split")
        return _count_by_field(jsonl, field_name)

    if method == SplitMethod.FILE:
        files = config.get("files", {})
        result = {}
        for split_name, split_path in files.items():
            split_file = base / split_path
            result[split_name] = _count_jsonl_lines(split_file)
        return result

    if method == SplitMethod.CUSTOM:
        filters = config.get("filters", {})
        result = {}
        for split_name, _filter_expr in filters.items():
            result[split_name] = 0  # custom filters need runtime eval
        return result

    return {}


def _count_jsonl_lines(path: Path | None) -> int:
    """Count non-empty lines in a JSONL file."""
    if not path or not path.exists():
        return 0
    try:
        with open(path) as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def _count_by_field(path: Path | None, field: str) -> dict[str, int]:
    """Count entries grouped by a JSON field value."""
    if not path or not path.exists():
        return {}
    counts: dict[str, int] = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    val = str(entry.get(field, "unknown"))
                    counts[val] = counts.get(val, 0) + 1
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return counts


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
