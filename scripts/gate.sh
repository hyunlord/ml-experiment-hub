#!/usr/bin/env bash
set -euo pipefail

echo "[gate] repo: $(pwd)"
echo "[gate] branch: $(git rev-parse --abbrev-ref HEAD)"
echo "[gate] git status:"
git status --porcelain || true

if ! command -v python3 >/dev/null 2>&1; then
  echo "[gate] ERROR: python3 not found. Install: brew install python"
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "[gate] ERROR: uv not found. Install: pip3 install -U uv"
  exit 1
fi

if [ ! -f uv.lock ]; then
  echo "[gate] ERROR: uv.lock not found"
  exit 1
fi

echo "[gate] uv sync --frozen"
uv sync --frozen

echo "[gate] run lint/format/type/test (if configured)"
# If your pyproject defines these tools, uv run will execute in the synced env.
uv run ruff check . || true
uv run ruff format --check . || true
uv run mypy . || true
uv run pytest -q || true

echo "[gate] smoke (time budget 90s)"
uv run python -m ml_experiment_hub.smoke --seconds 90 || true

echo "[gate] done"
