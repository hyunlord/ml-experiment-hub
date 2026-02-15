"""Comprehensive system information collector.

Collects CPU, RAM, Disk, Network, GPU, and process information
using psutil (direct import) and nvidia-smi (subprocess).
All blocking calls are wrapped in asyncio.to_thread() for async safety.
"""

import asyncio
import logging
import os
import platform
import shutil
import time
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IO rate tracker — stores previous counters to compute deltas
# ---------------------------------------------------------------------------

_prev_disk_io: dict[str, Any] | None = None
_prev_disk_io_time: float = 0.0
_prev_net_io: dict[str, Any] | None = None
_prev_net_io_time: float = 0.0


def _reset_io_trackers() -> None:
    """Reset IO rate trackers (e.g. on service restart)."""
    global _prev_disk_io, _prev_disk_io_time, _prev_net_io, _prev_net_io_time
    _prev_disk_io = None
    _prev_disk_io_time = 0.0
    _prev_net_io = None
    _prev_net_io_time = 0.0


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------


def _collect_cpu() -> dict[str, Any]:
    """Collect CPU information (blocking — call via to_thread)."""
    info: dict[str, Any] = {}

    # Model name
    try:
        model = platform.processor()
        if not model or model == "":
            # Try /proc/cpuinfo on Linux
            try:
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if line.startswith("model name"):
                            model = line.split(":", 1)[1].strip()
                            break
            except OSError:
                pass
        if not model:
            model = platform.machine()
        info["model"] = model
    except Exception:
        info["model"] = platform.machine() or "Unknown"

    # Core counts
    info["physical_cores"] = psutil.cpu_count(logical=False) or 0
    info["logical_cores"] = psutil.cpu_count(logical=True) or 0

    # Overall utilization (non-blocking snapshot with minimal interval)
    info["percent"] = psutil.cpu_percent(interval=0.1)

    # Per-core utilization
    try:
        per_core = psutil.cpu_percent(interval=0, percpu=True)
        info["per_core_percent"] = [round(v, 1) for v in per_core]
    except Exception:
        info["per_core_percent"] = []

    # Frequency
    freq = psutil.cpu_freq()
    if freq:
        info["freq_current_mhz"] = round(freq.current, 0)
        info["freq_max_mhz"] = round(freq.max, 0) if freq.max else None
    else:
        info["freq_current_mhz"] = None
        info["freq_max_mhz"] = None

    # Load average (Unix only)
    try:
        load = os.getloadavg()
        info["load_avg_1m"] = round(load[0], 2)
        info["load_avg_5m"] = round(load[1], 2)
        info["load_avg_15m"] = round(load[2], 2)
    except (OSError, AttributeError):
        info["load_avg_1m"] = None
        info["load_avg_5m"] = None
        info["load_avg_15m"] = None

    # Top 5 CPU processes
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                pi = p.info
                if pi and pi.get("cpu_percent", 0) and pi["cpu_percent"] > 0:
                    procs.append(
                        {
                            "pid": pi["pid"],
                            "name": pi.get("name", ""),
                            "cpu_percent": round(pi.get("cpu_percent", 0), 1),
                            "memory_percent": round(pi.get("memory_percent", 0), 1),
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
        info["top_processes"] = procs[:5]
    except Exception:
        info["top_processes"] = []

    return info


# ---------------------------------------------------------------------------
# RAM
# ---------------------------------------------------------------------------


def _collect_ram() -> dict[str, Any]:
    """Collect RAM information (blocking — call via to_thread)."""
    mem = psutil.virtual_memory()
    info: dict[str, Any] = {
        "percent": mem.percent,
        "used_gb": round(mem.used / 1024**3, 1),
        "total_gb": round(mem.total / 1024**3, 1),
        "available_gb": round(mem.available / 1024**3, 1),
    }

    # cached and buffers (Linux only — these attrs may not exist on macOS)
    info["cached_gb"] = round(getattr(mem, "cached", 0) / 1024**3, 1)
    info["buffers_gb"] = round(getattr(mem, "buffers", 0) / 1024**3, 1)

    # Swap
    swap = psutil.swap_memory()
    info["swap_used_gb"] = round(swap.used / 1024**3, 1)
    info["swap_total_gb"] = round(swap.total / 1024**3, 1)
    info["swap_percent"] = swap.percent

    return info


# ---------------------------------------------------------------------------
# Disk
# ---------------------------------------------------------------------------


def _collect_disk() -> dict[str, Any]:
    """Collect disk information (blocking — call via to_thread)."""
    global _prev_disk_io, _prev_disk_io_time

    info: dict[str, Any] = {}

    # Per-partition usage
    partitions = []
    seen_devices: set[str] = set()
    for part in psutil.disk_partitions(all=False):
        # Skip duplicates and virtual filesystems
        if part.device in seen_devices:
            continue
        seen_devices.add(part.device)
        try:
            usage = psutil.disk_usage(part.mountpoint)
            partitions.append(
                {
                    "mountpoint": part.mountpoint,
                    "device": part.device,
                    "fstype": part.fstype,
                    "used_gb": round(usage.used / 1024**3, 1),
                    "total_gb": round(usage.total / 1024**3, 1),
                    "free_gb": round(usage.free / 1024**3, 1),
                    "percent": round(usage.percent, 1),
                }
            )
        except (PermissionError, OSError):
            continue
    info["partitions"] = partitions

    # IO counters (compute rate from previous sample)
    try:
        counters = psutil.disk_io_counters()
        now = time.monotonic()
        if counters:
            current = {
                "read_bytes": counters.read_bytes,
                "write_bytes": counters.write_bytes,
            }
            if _prev_disk_io and _prev_disk_io_time > 0:
                dt = now - _prev_disk_io_time
                if dt > 0:
                    info["io"] = {
                        "read_mb_s": round(
                            (current["read_bytes"] - _prev_disk_io["read_bytes"]) / dt / 1024**2,
                            1,
                        ),
                        "write_mb_s": round(
                            (current["write_bytes"] - _prev_disk_io["write_bytes"]) / dt / 1024**2,
                            1,
                        ),
                        "read_total_gb": round(current["read_bytes"] / 1024**3, 1),
                        "write_total_gb": round(current["write_bytes"] / 1024**3, 1),
                    }
                else:
                    info["io"] = None
            else:
                # First call — store counters, no rate yet
                info["io"] = None
            _prev_disk_io = current
            _prev_disk_io_time = now
        else:
            info["io"] = None
    except Exception:
        info["io"] = None

    return info


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------


def _collect_network() -> dict[str, Any]:
    """Collect network information (blocking — call via to_thread)."""
    global _prev_net_io, _prev_net_io_time

    info: dict[str, Any] = {}
    now = time.monotonic()

    try:
        per_nic = psutil.net_io_counters(pernic=True)
        interfaces = []

        for name, counters in per_nic.items():
            # Skip loopback
            if name.startswith("lo"):
                continue

            iface: dict[str, Any] = {
                "name": name,
                "bytes_sent_gb": round(counters.bytes_sent / 1024**3, 2),
                "bytes_recv_gb": round(counters.bytes_recv / 1024**3, 2),
            }

            # Compute rates from previous sample
            if _prev_net_io and name in _prev_net_io:
                dt = now - _prev_net_io_time
                if dt > 0:
                    prev = _prev_net_io[name]
                    iface["upload_mb_s"] = round(
                        (counters.bytes_sent - prev["bytes_sent"]) / dt / 1024**2,
                        2,
                    )
                    iface["download_mb_s"] = round(
                        (counters.bytes_recv - prev["bytes_recv"]) / dt / 1024**2,
                        2,
                    )
                else:
                    iface["upload_mb_s"] = 0
                    iface["download_mb_s"] = 0
            else:
                iface["upload_mb_s"] = 0
                iface["download_mb_s"] = 0

            interfaces.append(iface)

        info["interfaces"] = interfaces

        # Store current counters for next call
        _prev_net_io = {
            name: {"bytes_sent": c.bytes_sent, "bytes_recv": c.bytes_recv}
            for name, c in per_nic.items()
        }
        _prev_net_io_time = now
    except Exception:
        info["interfaces"] = []

    return info


# ---------------------------------------------------------------------------
# GPU (nvidia-smi subprocess)
# ---------------------------------------------------------------------------


async def _collect_gpu() -> dict[str, Any]:
    """Collect GPU information via nvidia-smi (async subprocess)."""
    info: dict[str, Any] = {"gpus": [], "gpu_type": "none"}

    if not shutil.which("nvidia-smi"):
        # Check for Apple Silicon
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            info["gpu_type"] = "apple_silicon"
            # Collect basic Apple Silicon info
            try:
                mem = psutil.virtual_memory()
                info["apple_silicon"] = {
                    "chip": platform.processor() or "Apple Silicon",
                    "unified_memory_total_gb": round(mem.total / 1024**3, 1),
                    "unified_memory_used_gb": round(mem.used / 1024**3, 1),
                    "unified_memory_percent": mem.percent,
                    "metal_supported": True,
                }
            except Exception:
                info["apple_silicon"] = {"chip": "Apple Silicon", "metal_supported": True}
        return info

    info["gpu_type"] = "nvidia"

    try:
        # Extended query with clock, PCIe, CUDA version
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,"
            "temperature.gpu,power.draw,power.limit,fan.speed,"
            "clocks.current.graphics,clocks.current.memory,"
            "pcie.link.gen.current,pcie.link.width.current,"
            "driver_version",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        lines = stdout.decode().strip().split("\n")

        gpus = []
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 6:
                continue

            def _parse_float(val: str) -> float | None:
                if val in ("[N/A]", "N/A", "[Not Supported]", "Not Supported", ""):
                    return None
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None

            def _parse_int(val: str) -> int | None:
                if val in ("[N/A]", "N/A", "[Not Supported]", "Not Supported", ""):
                    return None
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return None

            mem_used = _parse_float(parts[3]) or 0
            mem_total = _parse_float(parts[4]) or 1

            gpu: dict[str, Any] = {
                "index": _parse_int(parts[0]) or 0,
                "name": parts[1],
                "util": _parse_float(parts[2]) or 0,
                "memory_used_mb": mem_used,
                "memory_total_mb": mem_total,
                "memory_percent": round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0,
                "temperature": _parse_float(parts[5]),
                "power_draw_w": _parse_float(parts[6]) if len(parts) > 6 else None,
                "power_limit_w": _parse_float(parts[7]) if len(parts) > 7 else None,
                "fan_speed": _parse_float(parts[8]) if len(parts) > 8 else None,
                "clock_graphics_mhz": _parse_int(parts[9]) if len(parts) > 9 else None,
                "clock_memory_mhz": _parse_int(parts[10]) if len(parts) > 10 else None,
                "pcie_gen": _parse_int(parts[11]) if len(parts) > 11 else None,
                "pcie_width": _parse_int(parts[12]) if len(parts) > 12 else None,
                "driver_version": parts[13] if len(parts) > 13 else None,
            }

            # Temperature fallback
            if gpu["temperature"] is None:
                gpu["temperature"] = await _get_gpu_temp_fallback(gpu["index"])

            gpus.append(gpu)

        info["gpus"] = gpus

        # Get CUDA version separately (nvidia-smi doesn't have it in CSV query)
        cuda_version = await _get_cuda_version()
        if cuda_version:
            for gpu in info["gpus"]:
                gpu["cuda_version"] = cuda_version

        # Get per-GPU processes
        gpu_processes = await _get_gpu_processes()
        for gpu in info["gpus"]:
            gpu["processes"] = gpu_processes.get(gpu["index"], [])

    except Exception:
        logger.debug("GPU collection failed", exc_info=True)

    return info


async def _get_gpu_temp_fallback(gpu_index: int) -> float | None:
    """Try alternative methods to get GPU temperature."""
    import glob as glob_mod

    # Method 1: nvidia-smi -q verbose
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

    # Method 2: Linux thermal zones
    try:
        for zone_dir in sorted(glob_mod.glob("/sys/class/thermal/thermal_zone*")):
            try:
                with open(f"{zone_dir}/type") as f:
                    zone_type = f.read().strip().lower()
                if "gpu" in zone_type:
                    with open(f"{zone_dir}/temp") as f:
                        raw = int(f.read().strip())
                    return raw / 1000.0 if raw > 1000 else float(raw)
            except (OSError, ValueError):
                continue
    except Exception:
        pass

    return None


async def _get_cuda_version() -> str | None:
    """Get CUDA version from nvidia-smi."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        for line in stdout.decode().split("\n"):
            if "CUDA Version" in line:
                # Parse "CUDA Version: 12.6"
                parts = line.split("CUDA Version:")
                if len(parts) >= 2:
                    return parts[1].strip().split()[0].strip()
    except Exception:
        pass
    return None


async def _get_gpu_processes() -> dict[int, list[dict[str, Any]]]:
    """Get processes using each GPU."""
    result: dict[int, list[dict[str, Any]]] = {}
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)

        # Also get GPU index to UUID mapping
        proc2 = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=index,uuid",
            "--format=csv,noheader",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout2, _ = await asyncio.wait_for(proc2.communicate(), timeout=5.0)

        uuid_to_index: dict[str, int] = {}
        for line in stdout2.decode().strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                uuid_to_index[parts[1]] = int(parts[0])

        for line in stdout.decode().strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                gpu_uuid = parts[0]
                gpu_idx = uuid_to_index.get(gpu_uuid, 0)
                try:
                    mem_mb = float(parts[3])
                except (ValueError, TypeError):
                    mem_mb = 0

                if gpu_idx not in result:
                    result[gpu_idx] = []
                result[gpu_idx].append(
                    {
                        "pid": int(parts[1]),
                        "name": parts[2],
                        "gpu_memory_mb": mem_mb,
                    }
                )
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Processes (training-related)
# ---------------------------------------------------------------------------


def _collect_processes() -> list[dict[str, Any]]:
    """Collect training-related processes (blocking — call via to_thread)."""
    training_keywords = {"python", "train", "torch", "lightning", "accelerate", "deepspeed"}
    processes = []

    for p in psutil.process_iter(
        ["pid", "name", "cmdline", "cpu_percent", "memory_percent", "memory_info", "create_time"]
    ):
        try:
            pi = p.info
            if not pi:
                continue

            name = pi.get("name", "")
            cmdline = pi.get("cmdline") or []
            cmdline_str = " ".join(cmdline).lower()

            # Filter: only training-related processes
            is_training = any(kw in name.lower() or kw in cmdline_str for kw in training_keywords)
            if not is_training:
                continue

            # Build display name from cmdline
            display_name = " ".join(cmdline[:3]) if cmdline else name

            mem_info = pi.get("memory_info")
            memory_mb = round(mem_info.rss / 1024**2, 1) if mem_info else 0

            create_time = pi.get("create_time", 0)
            runtime_seconds = round(time.time() - create_time) if create_time else 0

            processes.append(
                {
                    "pid": pi["pid"],
                    "name": display_name[:80],  # Truncate long command lines
                    "cpu_percent": round(pi.get("cpu_percent", 0), 1),
                    "memory_percent": round(pi.get("memory_percent", 0), 1),
                    "memory_mb": memory_mb,
                    "runtime_seconds": runtime_seconds,
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
    return processes[:20]  # Cap at 20


# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------


def _collect_platform() -> dict[str, Any]:
    """Collect platform information."""
    info: dict[str, Any] = {
        "system": platform.system(),
        "hostname": platform.node(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
    }

    # Uptime
    try:
        info["uptime_seconds"] = round(time.time() - psutil.boot_time())
    except Exception:
        info["uptime_seconds"] = None

    return info


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def collect_system_info() -> dict[str, Any]:
    """Collect comprehensive system information.

    Returns a dict with keys: cpu, ram, disk, network, gpus, gpu_type,
    processes, platform. All blocking psutil calls run in a thread pool.

    This is the single source of truth for system stats.
    """
    # Run CPU, RAM, Disk, Network, Processes, Platform in thread pool (blocking)
    # GPU runs as async subprocess
    cpu_task = asyncio.to_thread(_collect_cpu)
    ram_task = asyncio.to_thread(_collect_ram)
    disk_task = asyncio.to_thread(_collect_disk)
    net_task = asyncio.to_thread(_collect_network)
    proc_task = asyncio.to_thread(_collect_processes)
    platform_task = asyncio.to_thread(_collect_platform)
    gpu_task = _collect_gpu()

    cpu, ram, disk, network, processes, plat, gpu = await asyncio.gather(
        cpu_task,
        ram_task,
        disk_task,
        net_task,
        proc_task,
        platform_task,
        gpu_task,
    )

    return {
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
        "network": network,
        "gpus": gpu.get("gpus", []),
        "gpu_type": gpu.get("gpu_type", "none"),
        "apple_silicon": gpu.get("apple_silicon"),
        "processes": processes,
        "platform": plat,
    }
