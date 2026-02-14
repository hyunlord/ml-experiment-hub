"""System information API for GPU detection, auto-config, and health checks."""

import logging
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


def _get_gpu_info() -> dict[str, str | float | bool]:
    """Detect GPU name, VRAM, and unified memory status.

    Returns fallback values if no GPU is available.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return {
                "name": "No GPU detected",
                "vram_gb": 0,
                "unified": False,
                "available": False,
            }

        props = torch.cuda.get_device_properties(0)
        vram_gb = round(props.total_memory / 1024**3, 1)
        gpu_name = props.name

        # Detect unified memory (DGX Spark GB10, Jetson, etc.)
        unified_keywords = ("gb10", "dgx spark", "grace", "jetson", "tegra")
        name_lower = gpu_name.lower()
        unified = any(kw in name_lower for kw in unified_keywords)
        if not unified and vram_gb > 100:
            unified = True

        return {
            "name": gpu_name,
            "vram_gb": vram_gb,
            "unified": unified,
            "available": True,
        }
    except Exception as e:
        logger.warning("GPU detection failed: %s", e)
        return {
            "name": "Detection failed",
            "vram_gb": 0,
            "unified": False,
            "available": False,
        }


def _compute_auto_config(vram_gb: float, unified: bool, freeze_backbone: bool) -> dict[str, int]:
    """Compute expected batch size and accumulation for auto-configure.

    Mirrors the logic in vlm_quantization/src/utils/gpu_config.py.
    """
    if vram_gb == 0:
        return {"batch_size": 32, "accumulate_grad_batches": 8, "num_workers": 2}

    # Unified memory: reserve ~30GB for OS
    if unified:
        gpu_usable_gb = min(vram_gb, max(vram_gb - 30, vram_gb * 0.7))
    else:
        gpu_usable_gb = vram_gb

    base_per_sample = 0.11 if freeze_backbone else 0.28
    view_multiplier = 1.3 if freeze_backbone else 2.4
    per_sample = base_per_sample * view_multiplier
    model_overhead = 2.0 if freeze_backbone else 4.0
    utilization = 0.65

    available = gpu_usable_gb * utilization - model_overhead
    optimal_batch = int(available / per_sample)
    optimal_batch = max(32, (optimal_batch // 32) * 32)

    target_effective_batch = 256
    if optimal_batch >= target_effective_batch:
        accum = 1
        batch_size = optimal_batch
    else:
        batch_size = optimal_batch
        accum = max(1, -(-target_effective_batch // batch_size))

    import os

    cpu_count = os.cpu_count() or 4
    worker_cap = 12 if unified else 8
    num_workers = min(cpu_count, worker_cap, max(2, batch_size // 32))

    return {
        "batch_size": batch_size,
        "accumulate_grad_batches": accum,
        "num_workers": num_workers,
    }


@router.get("/gpu-info")
async def gpu_info() -> dict[str, str | float | bool | dict[str, dict[str, int]]]:
    """Return current GPU info and auto_configure preview.

    Used by the frontend to show expected batch size when batch_size=auto.

    Returns:
        {name, vram_gb, unified, available, auto_config: {frozen: {...}, unfrozen: {...}}}
    """
    info = _get_gpu_info()

    # Type narrowing for mypy
    vram_gb = float(info["vram_gb"])
    unified = bool(info["unified"])

    auto_config = {}
    if info["available"]:
        auto_config["frozen"] = _compute_auto_config(
            vram_gb,
            unified,
            freeze_backbone=True,
        )
        auto_config["unfrozen"] = _compute_auto_config(
            vram_gb,
            unified,
            freeze_backbone=False,
        )
    else:
        auto_config["frozen"] = {"batch_size": 32, "accumulate_grad_batches": 8, "num_workers": 2}
        auto_config["unfrozen"] = {"batch_size": 32, "accumulate_grad_batches": 8, "num_workers": 2}

    return {**info, "auto_config": auto_config}


async def _get_gpu_temp_fallback(gpu_index: int) -> float | None:
    """Try alternative methods to get GPU temperature when nvidia-smi CSV returns N/A.

    Fallback chain:
    1. nvidia-smi -q (verbose output parsing)
    2. /sys/class/thermal/ (Linux thermal zones)
    """
    import asyncio
    import glob

    # Method 1: nvidia-smi -q -i <index> (verbose query)
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "-q",
            "-i",
            str(gpu_index),
            "-d",
            "TEMPERATURE",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        for line in stdout.decode().split("\n"):
            if "GPU Current Temp" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    temp_str = parts[1].strip().replace(" C", "").strip()
                    return float(temp_str)
    except Exception:
        pass

    # Method 2: Linux thermal zones (common on ARM/Jetson/DGX Spark)
    try:
        for zone_dir in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
            type_path = f"{zone_dir}/type"
            temp_path = f"{zone_dir}/temp"
            try:
                with open(type_path) as f:
                    zone_type = f.read().strip().lower()
                if "gpu" in zone_type or "gpu-thermal" in zone_type:
                    with open(temp_path) as f:
                        raw = int(f.read().strip())
                    return raw / 1000.0 if raw > 1000 else float(raw)
            except (OSError, ValueError):
                continue
    except Exception:
        pass

    return None


@router.get("/stats")
async def system_stats() -> dict[str, Any]:
    """Real-time system stats for the System Dashboard.

    Returns GPU, CPU, RAM, and disk information without requiring
    an active training run.
    """
    import asyncio
    import shutil

    stats: dict[str, Any] = {}

    # --- GPU via nvidia-smi ---
    if shutil.which("nvidia-smi"):
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,fan.speed,driver_version",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            lines = stdout.decode().strip().split("\n")

            gpus = []
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    mem_used = float(parts[3])
                    mem_total = float(parts[4])
                    gpus.append(
                        {
                            "index": int(parts[0]),
                            "name": parts[1],
                            "util": float(parts[2]),
                            "memory_used_mb": mem_used,
                            "memory_total_mb": mem_total,
                            "memory_percent": round(mem_used / mem_total * 100, 1)
                            if mem_total > 0
                            else 0,
                            "temperature": float(parts[5])
                            if parts[5] not in ("[N/A]", "N/A", "")
                            else None,
                            "power_draw_w": float(parts[6])
                            if len(parts) > 6 and parts[6] not in ("[N/A]", "N/A", "")
                            else None,
                            "fan_speed": float(parts[7])
                            if len(parts) > 7 and parts[7] not in ("[N/A]", "N/A", "")
                            else None,
                            "driver_version": parts[8] if len(parts) > 8 else None,
                        }
                    )
            # Fallback: if temperature is null, try thermal zones or nvidia-smi -q
            for gpu in gpus:
                if gpu["temperature"] is None:
                    gpu["temperature"] = await _get_gpu_temp_fallback(gpu["index"])

            stats["gpus"] = gpus
        except Exception:
            stats["gpus"] = []
    else:
        stats["gpus"] = []

    # --- CPU ---
    try:
        proc = await asyncio.create_subprocess_exec(
            "python",
            "-c",
            "import psutil,json;print(json.dumps({'percent':psutil.cpu_percent(interval=0.1),'count':psutil.cpu_count(),'freq':psutil.cpu_freq().current if psutil.cpu_freq() else None}))",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        import json

        stats["cpu"] = json.loads(stdout.decode().strip())
    except Exception:
        stats["cpu"] = {"percent": None, "count": None, "freq": None}

    # --- RAM ---
    try:
        proc = await asyncio.create_subprocess_exec(
            "python",
            "-c",
            "import psutil,json;m=psutil.virtual_memory();print(json.dumps({'percent':m.percent,'used_gb':round(m.used/1024**3,1),'total_gb':round(m.total/1024**3,1)}))",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        import json

        stats["ram"] = json.loads(stdout.decode().strip())
    except Exception:
        stats["ram"] = {"percent": None, "used_gb": None, "total_gb": None}

    # --- Disk ---
    try:
        import shutil as _shutil

        usage = _shutil.disk_usage("/")
        stats["disk"] = {
            "used_gb": round(usage.used / 1024**3, 1),
            "total_gb": round(usage.total / 1024**3, 1),
            "free_gb": round(usage.free / 1024**3, 1),
            "percent": round(usage.used / usage.total * 100, 1),
        }
    except Exception:
        stats["disk"] = {"used_gb": None, "total_gb": None, "free_gb": None, "percent": None}

    return stats


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint for Docker healthcheck and monitoring.

    Checks:
    - Database connectivity
    - Disk space
    - Log directory stats

    Returns:
        Health status with component details.
    """
    from backend.models.database import async_session_maker
    from backend.services.health_checks import check_disk_space
    from backend.services.log_manager import get_log_dir_stats

    checks: dict[str, Any] = {"status": "healthy"}
    all_ok = True

    # DB check
    try:
        async with async_session_maker() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}
        all_ok = False

    # Disk check
    disk = check_disk_space()
    checks["disk"] = disk
    if not disk["ok"]:
        all_ok = False

    # Log stats
    checks["logs"] = get_log_dir_stats()

    if not all_ok:
        checks["status"] = "degraded"

    return checks
