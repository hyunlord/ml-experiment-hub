#!/usr/bin/env bash
set -euo pipefail

echo "[gate] repo: $(pwd)"
echo "[gate] git status:"
git status --porcelain || true

# --- Python first (common for ML) ---
if [ -f pyproject.toml ] || [ -f requirements.txt ]; then
  echo "[gate] python deps (best effort)"
  python -m pip install -U pip || true
  pip install -e ".[dev]" || true

  echo "[gate] lint/format/type/test"
  ruff check . || true
  ruff format --check . || true
  mypy . || true
  pytest -q || true

  echo "[gate] ML smoke (if provided)"
  # You should implement at least one of these entrypoints:
  # - python -m ml_hub.smoke
  # - ./scripts/smoke_train.sh
  # - make smoke
  python -m ml_hub.smoke || true
  ./scripts/smoke_train.sh || true
  make smoke || true
fi

# --- Node/TS UI (if exists) ---
if [ -f package.json ]; then
  echo "[gate] npm ci"
  npm ci

  echo "[gate] format/lint/type/test"
  npm run -s format:check || true
  npm run -s lint || true
  npm run -s typecheck || true
  npm run -s test || true
  npm run -s smoke || true
fi

echo "[gate] done"
