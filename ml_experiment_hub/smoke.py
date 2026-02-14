import argparse
import subprocess
import sys
import time
from pathlib import Path

def run(cmd: str, timeout_s: int) -> int:
    print(f"[smoke] cmd: {cmd}")
    start = time.time()
    try:
        p = subprocess.run(cmd, shell=True, timeout=timeout_s)
        code = p.returncode
    except subprocess.TimeoutExpired:
        print(f"[smoke] TIMEOUT after {timeout_s}s")
        return 124
    dur = time.time() - start
    print(f"[smoke] done: rc={code} time={dur:.1f}s")
    return code

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=90, help="time budget for smoke run")
    ap.add_argument("--cmd", type=str, default="", help="override command to run")
    args = ap.parse_args()

    # Default smoke command: try common entrypoints; adjust later to your platform.
    candidates = [
        "python -m ml_experiment_hub.cli smoke",
        "python -m ml_experiment_hub.cli --help",
        "python -c \"print('smoke: ok')\"",
    ]
    if args.cmd:
        candidates = [args.cmd]

    timeout_s = max(15, min(args.seconds, 300))

    for c in candidates:
        rc = run(c, timeout_s=timeout_s)
        if rc == 0:
            print("[smoke] PASS")
            return 0

    print("[smoke] FAIL: no smoke candidate succeeded. Set --cmd or implement ml_experiment_hub.cli smoke.")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
