#!/bin/bash
# tools/codex_dispatch.sh
# Claude Code가 이 스크립트를 호출해서 Codex Cloud에 티켓을 보냄
#
# 사용법:
#   bash tools/codex_dispatch.sh tickets/t-010-fix-input.md
#   bash tools/codex_dispatch.sh tickets/t-010-fix-input.md t/010-fix-input

set -euo pipefail

TICKET_FILE="$1"
BRANCH="${2:-}"
ENV_ID="${CODEX_ENV_MLHUB:?ERROR: CODEX_ENV_MLHUB 환경변수를 설정하세요}"

if [ ! -f "$TICKET_FILE" ]; then
  echo "[codex-dispatch] ERROR: 파일 없음: $TICKET_FILE"
  exit 1
fi

# 브랜치명 자동 추출 (없으면 파일명에서)
if [ -z "$BRANCH" ]; then
  SLUG=$(basename "$TICKET_FILE" .md)
  BRANCH="t/${SLUG}"
fi

TICKET_CONTENT=$(cat "$TICKET_FILE")

echo "╔══════════════════════════════════════╗"
echo "║  Codex Cloud Dispatch                ║"
echo "╠══════════════════════════════════════╣"
echo "║  ENV:    $ENV_ID"
echo "║  Branch: $BRANCH"
echo "║  Ticket: $TICKET_FILE"
echo "╚══════════════════════════════════════╝"

codex cloud exec \
  --env "$ENV_ID" \
  "You are implementing a ticket for the WorldSim project (Godot 4.6, GDScript).

Branch to work on: ${BRANCH}

Read AGENTS.md in the repo root for project conventions.

=== TICKET START ===
${TICKET_CONTENT}
=== TICKET END ===

After implementation:
1. Commit all changes to branch '${BRANCH}'
2. Run: bash scripts/gate.sh
3. If gate fails, fix and retry until it passes
4. Create a PR to lead/main with a clear summary"

echo "[codex-dispatch] ✅ Task submitted to Codex Cloud"