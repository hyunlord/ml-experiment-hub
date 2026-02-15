#!/usr/bin/env bash
# =============================================================================
# ML Experiment Hub - Database Reset
# DGX Spark에서 실행: ./scripts/reset-db.sh
# Stops containers, deletes DB files, restarts with fresh database.
# =============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}ML Experiment Hub - Database Reset${NC}"
echo "══════════════════════════════════════════"

# ── Step 1: Stop containers ─────────────────────────────────────────────
echo -e "${GREEN}Stopping containers...${NC}"
docker compose down

# ── Step 2: Remove database files ───────────────────────────────────────
echo -e "${GREEN}Removing database files...${NC}"
rm -f ./data/*.db ./data/*.db-shm ./data/*.db-wal 2>/dev/null || true
echo "  Cleaned ./data/*.db"

# ── Step 3: Restart with fresh database ─────────────────────────────────
echo -e "${GREEN}Starting with fresh database...${NC}"
docker compose up -d

# ── Step 4: Wait and verify ─────────────────────────────────────────────
echo -e "${GREEN}Waiting for startup...${NC}"
sleep 5

echo -e "${GREEN}Health check...${NC}"
if curl -sf http://localhost:3000/api/projects | head -c 200; then
    echo ""
    echo -e "${GREEN}Database reset complete.${NC}"
else
    echo ""
    echo -e "${RED}Health check failed. Check logs:${NC}"
    echo "  docker compose logs backend --tail 20"
    exit 1
fi

echo ""
echo "══════════════════════════════════════════"
echo -e "Check: ${YELLOW}docker compose logs backend --tail 20${NC}"
