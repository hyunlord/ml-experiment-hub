"""System information API for GPU detection and auto-configuration preview."""

import logging

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
