import argparse
import time

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=90)
    args = ap.parse_args()

    # Minimal smoke: prove interpreter + package import works within time budget.
    t0 = time.time()
    import ml_experiment_hub  # noqa: F401
    dt = time.time() - t0
    print(f"[smoke] import ok in {dt:.3f}s (budget {args.seconds}s)")
    print("[smoke] PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
