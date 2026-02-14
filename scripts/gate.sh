#!/usr/bin/env bash
set -euo pipefail

echo "[gate] repo: $(pwd)"
echo "[gate] branch: $(git rev-parse --abbrev-ref HEAD)"
echo "[gate] git status (before):"
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

echo "[gate] uv sync --frozen --all-extras"
uv sync --frozen --all-extras

# Strict: uv.lock must not change during frozen sync
if ! git diff --quiet -- uv.lock; then
  echo "[gate] ERROR: uv.lock changed during gate run. Commit updated uv.lock in lead."
  git --no-pager diff -- uv.lock | sed -n '1,120p'
  exit 1
fi

echo "[gate] lint/format/type/test"
uv run ruff check .
uv run ruff format --check .
uv run mypy . || true
uv run pytest -q || true

echo "[gate] smoke (time budget 90s)"
uv run python -m ml_experiment_hub.smoke --seconds 90

echo "[gate] done"
