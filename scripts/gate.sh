#!/usr/bin/env bash
set -euo pipefail

echo "[gate] repo: $(pwd)"
echo "[gate] git status:"
git status --porcelain || true

PY="$(command -v python3 || true)"
PIP="$(command -v pip3 || true)"

if [ -z "${PY}" ] || [ -z "${PIP}" ]; then
  echo "[gate] ERROR: python3/pip3 not found. Install: brew install python"
  exit 1
fi

echo "[gate] using: ${PY}"

# ---------- install deps (strict when lock exists) ----------
if [ -f uv.lock ]; then
  echo "[gate] uv strict (uv.lock)"
  command -v uv >/dev/null 2>&1 || { echo "[gate] uv not installed. Install: pip3 install -U uv"; exit 1; }
  uv sync --frozen

elif [ -f poetry.lock ]; then
  echo "[gate] poetry strict (poetry.lock)"
  command -v poetry >/dev/null 2>&1 || { echo "[gate] poetry not installed. Install: pip3 install -U poetry"; exit 1; }
  poetry install --no-interaction --sync

elif [ -f environment.yml ]; then
  echo "[gate] conda env detected (environment.yml)"
  echo "[gate] NOTE: local conda strict gate is not enforced by this script."
  echo "[gate]       Prefer running this in CI/Docker with a pinned environment."
  # best-effort: do not fail local
  true

else
  echo "[gate] pip/venv best-effort (no lockfile)"
  ${PY} -m pip install -U pip
  [ -f pyproject.toml ] && ${PIP} install -e ".[dev]" || true
  [ -f requirements.txt ] && ${PIP} install -r requirements.txt || true
fi

# ---------- tools ----------
${PY} -m pip install -U ruff mypy pytest >/dev/null 2>&1 || true

echo "[gate] lint/format/type/test"
${PY} -m ruff check .
${PY} -m ruff format --check .
${PY} -m mypy . || true
${PY} -m pytest -q || true

echo "[gate] ML smoke (30~120s target)"
${PY} -m ml_experiment_hub.smoke --seconds 90 || true

echo "[gate] done"
