"""System information collector for the lightweight agent.

Mirrors the hub's backend/services/system_info.py but as a standalone
module with no hub dependencies. Only requires psutil.
"""

import asyncio
import logging
import platform
import subprocess
import time
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IO rate tracking (module-level state for delta computation)
# ---------------------------------------------------------------------------

_prev_disk_io: dict[str, Any] | None = None
_prev_net_io: dict[str, Any] | None = None
_prev_ts: float = 0.0


def _collect_cpu() -> dict[str, Any]:
    """Collect CPU information."""
    freq = psutil.cpu_freq()
    load1, load5, load15 = psutil.getloadavg()

    # CPU model
    model = platform.processor() or "Unknown"
    if platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        model = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass

    return {
        "model": model,
        "physical_cores": psutil.cpu_count(logical=False) or 0,
        "logical_cores": psutil.cpu_count(logical=True) or 0,
        "percent": psutil.cpu_percent(interval=0.1),
        "per_core_percent": psutil.cpu_percent(interval=0, percpu=True),
        "frequency_mhz": round(freq.current, 0) if freq else None,
        "load_avg": {"1min": round(load1, 2), "5min": round(load5, 2), "15min": round(load15, 2)},
    }


def _collect_ram() -> dict[str, Any]:
    """Collect RAM information."""
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return {
        "total_gb": round(vm.total / 1024**3, 1),
        "used_gb": round(vm.used / 1024**3, 1),
        "available_gb": round(vm.available / 1024**3, 1),
        "percent": vm.percent,
        "cached_gb": round(getattr(vm, "cached", 0) / 1024**3, 1),
        "buffers_gb": round(getattr(vm, "buffers", 0) / 1024**3, 1),
        "swap_total_gb": round(sw.total / 1024**3, 1),
        "swap_used_gb": round(sw.used / 1024**3, 1),
        "swap_percent": sw.percent,
    }


def _collect_disk() -> dict[str, Any]:
    """Collect disk partition and IO information."""
    global _prev_disk_io, _prev_ts

    partitions = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            partitions.append(
                {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / 1024**3, 1),
                    "used_gb": round(usage.used / 1024**3, 1),
                    "free_gb": round(usage.free / 1024**3, 1),
                    "percent": usage.percent,
                }
            )
        except (PermissionError, OSError):
            continue

    # IO rates
    io_read_mb_s = 0.0
    io_write_mb_s = 0.0
    now = time.monotonic()
    try:
        counters = psutil.disk_io_counters()
        if counters and _prev_disk_io is not None:
            dt = now - _prev_ts
            if dt > 0:
                io_read_mb_s = round(
                    (counters.read_bytes - _prev_disk_io["read"]) / dt / 1024**2, 1
                )
                io_write_mb_s = round(
                    (counters.write_bytes - _prev_disk_io["write"]) / dt / 1024**2, 1
                )
        if counters:
            _prev_disk_io = {"read": counters.read_bytes, "write": counters.write_bytes}
            _prev_ts = now
    except Exception:
        pass

    return {
        "partitions": partitions,
        "io_read_mb_s": max(0, io_read_mb_s),
        "io_write_mb_s": max(0, io_write_mb_s),
    }


def _collect_network() -> dict[str, Any]:
    """Collect network interface information."""
    global _prev_net_io

    now = time.monotonic()
    interfaces = []
    try:
        counters = psutil.net_io_counters(pernic=True)
        for name, c in counters.items():
            if name == "lo" or name.startswith("lo"):
                continue
            iface: dict[str, Any] = {
                "name": name,
                "bytes_sent": c.bytes_sent,
                "bytes_recv": c.bytes_recv,
                "upload_mb_s": 0.0,
                "download_mb_s": 0.0,
            }
            if _prev_net_io and name in _prev_net_io:
                dt = now - _prev_net_io["_ts"]
                if dt > 0:
                    iface["upload_mb_s"] = round(
                        (c.bytes_sent - _prev_net_io[name]["sent"]) / dt / 1024**2, 2
                    )
                    iface["download_mb_s"] = round(
                        (c.bytes_recv - _prev_net_io[name]["recv"]) / dt / 1024**2, 2
                    )
            interfaces.append(iface)

        _prev_net_io = {"_ts": now}
        for name, c in counters.items():
            _prev_net_io[name] = {"sent": c.bytes_sent, "recv": c.bytes_recv}
    except Exception:
        pass

    return {"interfaces": interfaces}


def _collect_gpus() -> list[dict[str, Any]]:
    """Collect GPU information via nvidia-smi."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,"
                "temperature.gpu,power.draw,power.limit,fan.speed,"
                "clocks.current.graphics,clocks.current.memory,"
                "pcie.link.gen.current,pcie.link.width.current,"
                "driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []

        gpus = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 14:
                continue

            def safe_float(s: str) -> float | None:
                try:
                    return float(s)
                except (ValueError, TypeError):
                    return None

            def safe_int(s: str) -> int | None:
                try:
                    return int(s)
                except (ValueError, TypeError):
                    return None

            mem_used = safe_float(parts[3]) or 0
            mem_total = safe_float(parts[4]) or 1
            gpus.append(
                {
                    "index": safe_int(parts[0]) or 0,
                    "name": parts[1],
                    "util": safe_float(parts[2]) or 0,
                    "memory_used_mb": mem_used,
                    "memory_total_mb": mem_total,
                    "memory_percent": round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0,
                    "temperature": safe_float(parts[5]),
                    "power_draw_w": safe_float(parts[6]),
                    "power_limit_w": safe_float(parts[7]),
                    "fan_percent": safe_float(parts[8]),
                    "clock_graphics_mhz": safe_float(parts[9]),
                    "clock_memory_mhz": safe_float(parts[10]),
                    "pcie_gen": safe_int(parts[11]),
                    "pcie_width": safe_int(parts[12]),
                    "driver_version": parts[13] if len(parts) > 13 else None,
                }
            )

        # Collect per-GPU processes
        try:
            proc_result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-compute-apps=pid,name,used_memory",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc_result.returncode == 0:
                for gpu in gpus:
                    gpu["processes"] = []
                for pline in proc_result.stdout.strip().split("\n"):
                    if not pline.strip():
                        continue
                    pp = [p.strip() for p in pline.split(",")]
                    if len(pp) >= 3:
                        proc_entry = {
                            "pid": int(pp[0]) if pp[0].isdigit() else 0,
                            "name": pp[1],
                            "gpu_memory_mb": safe_float(pp[2]) or 0,
                        }
                        if gpus:
                            gpus[0].setdefault("processes", []).append(proc_entry)
        except Exception:
            pass

        return gpus
    except FileNotFoundError:
        return []
    except Exception:
        logger.debug("GPU collection failed", exc_info=True)
        return []


def _collect_platform() -> dict[str, Any]:
    """Collect platform information."""
    boot_time = psutil.boot_time()
    uptime_s = time.time() - boot_time
    return {
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "uptime_hours": round(uptime_s / 3600, 1),
    }


async def collect_system_info() -> dict[str, Any]:
    """Collect all system information asynchronously."""
    loop = asyncio.get_event_loop()
    cpu, ram, disk, network, gpus, plat = await asyncio.gather(
        loop.run_in_executor(None, _collect_cpu),
        loop.run_in_executor(None, _collect_ram),
        loop.run_in_executor(None, _collect_disk),
        loop.run_in_executor(None, _collect_network),
        loop.run_in_executor(None, _collect_gpus),
        loop.run_in_executor(None, _collect_platform),
    )
    return {
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
        "network": network,
        "gpus": gpus,
        "platform": plat,
    }
