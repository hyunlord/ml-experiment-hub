#!/usr/bin/env bash
set -euo pipefail

echo "[gate] repo: $(pwd)"
echo "[gate] git status:"
git status --porcelain || true

# pick python executable (python3 preferred)
PY="$(command -v python3 || true)"
PIP="$(command -v pip3 || true)"

if [ -z "${PY}" ] || [ -z "${PIP}" ]; then
  echo "[gate] Python3/pip3 not found on this machine."
  echo "[gate] Install with: brew install python"
  echo "[gate] Skipping Python checks."
else
  echo "[gate] using: ${PY}"
fi

maybe_install_py_tools() {
  # Install tools only if missing; ignore failures to keep gate non-blocking on local machines
  if ! ${PY} -m ruff --version >/dev/null 2>&1; then
    ${PIP} install -U ruff >/dev/null 2>&1 || true
  fi
  if ! ${PY} -m mypy --version >/dev/null 2>&1; then
    ${PIP} install -U mypy >/dev/null 2>&1 || true
  fi
  if ! ${PY} -m pytest --version >/dev/null 2>&1; then
    ${PIP} install -U pytest >/dev/null 2>&1 || true
  fi
}

run_python_gate() {
  echo "[gate] python deps (best effort)"

  ${PY} -m pip install -U pip >/dev/null 2>&1 || true

  # repo-managed deps (best effort)
  if [ -f pyproject.toml ]; then
    ${PIP} install -e ".[dev]" >/dev/null 2>&1 || true
  fi
  if [ -f requirements.txt ]; then
    ${PIP} install -r requirements.txt >/dev/null 2>&1 || true
  fi

  maybe_install_py_tools

  echo "[gate] lint/format/type/test (best effort)"
  ${PY} -m ruff check . || true
  ${PY} -m ruff format --check . || true
  ${PY} -m mypy . || true
  ${PY} -m pytest -q || true

  echo "[gate] ML smoke (optional)"
  # If you later add one of these, gate will pick it up.
  ${PY} -m ml_experiment_hub.smoke || true
  [ -x ./scripts/smoke_train.sh ] && ./scripts/smoke_train.sh || true
  make smoke >/dev/null 2>&1 || true
}

# Run Python gate only if python exists and repo looks like python project
if [ -n "${PY}" ] && ( [ -f pyproject.toml ] || [ -f requirements.txt ] ); then
  run_python_gate
fi

# Node UI checks if present
if [ -f package.json ]; then
  echo "[gate] Node project detected"
  if [ -f package-lock.json ] || [ -f npm-shrinkwrap.json ]; then
    npm ci
  else
    npm install
  fi
  npm run -s lint || true
  npm run -s typecheck || true
  npm run -s test || true
  npm run -s smoke || true
fi

echo "[gate] done"
