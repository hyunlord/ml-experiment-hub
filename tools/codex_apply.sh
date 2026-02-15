#!/bin/bash
# Codex가 완료한 diff를 로컬에 적용
echo "[codex-apply] Applying latest Codex Cloud diff..."
codex apply
echo "[codex-apply] Done. Running gate..."
cd "$(git rev-parse --show-toplevel)"
bash scripts/gate.sh