"""Health check utilities for proactive error detection.

Provides:
- Disk space checks before checkpoint saves
- GPU temperature monitoring with alert thresholds
- OOM pattern detection in log lines
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)

# Minimum free disk space (bytes) before warning — 2 GB
DISK_WARNING_THRESHOLD = 2 * 1024 * 1024 * 1024

# GPU temperature thresholds (Celsius)
GPU_TEMP_WARNING = 85
GPU_TEMP_CRITICAL = 95

# OOM detection patterns
OOM_PATTERNS = [
    re.compile(r"CUDA out of memory", re.IGNORECASE),
    re.compile(r"RuntimeError:.*out of memory", re.IGNORECASE),
    re.compile(r"torch\.cuda\.OutOfMemoryError", re.IGNORECASE),
    re.compile(r"CUBLAS_STATUS_ALLOC_FAILED", re.IGNORECASE),
]


def check_disk_space(path: str | None = None) -> dict[str, int | bool | str]:
    """Check available disk space.

    Args:
        path: Path to check. Defaults to CHECKPOINT_BASE_DIR.

    Returns:
        Dict with total, used, free (bytes), ok (bool), message.
    """
    check_path = Path(path or settings.CHECKPOINT_BASE_DIR)
    # Fall back to current dir if path doesn't exist
    if not check_path.exists():
        check_path = Path(".")

    usage = shutil.disk_usage(str(check_path))
    ok = usage.free >= DISK_WARNING_THRESHOLD

    return {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "ok": ok,
        "message": "" if ok else f"Low disk space: {usage.free / (1024**3):.1f} GB free",
    }


def detect_oom(log_line: str) -> bool:
    """Check if a log line indicates an OOM error.

    Args:
        log_line: A single line of log output.

    Returns:
        True if OOM pattern detected.
    """
    return any(p.search(log_line) for p in OOM_PATTERNS)


def classify_error(log_lines: str) -> str | None:
    """Classify an error from log output into a human-readable category.

    Args:
        log_lines: Recent log output (last N lines).

    Returns:
        Error category string or None if unclassified.
    """
    if any(p.search(log_lines) for p in OOM_PATTERNS):
        return "OOM: GPU ran out of memory. Try reducing batch_size or model size."

    if re.search(r"No space left on device", log_lines, re.IGNORECASE):
        return "DISK_FULL: No disk space remaining. Free space or change checkpoint directory."

    if re.search(r"NCCL|nccl.*error", log_lines, re.IGNORECASE):
        return "NCCL_ERROR: Multi-GPU communication failure. Check GPU connections."

    if re.search(r"Segmentation fault|SIGSEGV", log_lines):
        return "SEGFAULT: Process crashed with segmentation fault."

    if re.search(r"Killed|signal 9|SIGKILL", log_lines):
        return "KILLED: Process killed by OS (likely OOM-killer)."

    return None


def check_gpu_temperatures(gpus: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Check GPU temperatures against thresholds.

    Args:
        gpus: List of GPU stat dicts from system_monitor (with 'temperature' key).

    Returns:
        List of warning dicts for overheating GPUs.
    """
    if not gpus:
        return []

    warnings = []
    for gpu in gpus:
        temp = gpu.get("temperature")
        if temp is None:
            continue

        if temp >= GPU_TEMP_CRITICAL:
            warnings.append(
                {
                    "gpu_index": gpu.get("index", 0),
                    "temperature": temp,
                    "level": "critical",
                    "message": f"GPU {gpu.get('index', 0)} at {temp}°C — CRITICAL! Risk of thermal throttling or shutdown.",
                }
            )
        elif temp >= GPU_TEMP_WARNING:
            warnings.append(
                {
                    "gpu_index": gpu.get("index", 0),
                    "temperature": temp,
                    "level": "warning",
                    "message": f"GPU {gpu.get('index', 0)} at {temp}°C — high temperature warning.",
                }
            )

    return warnings
