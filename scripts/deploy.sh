#!/usr/bin/env bash
# =============================================================================
# ML Experiment Hub - Deploy (Code Update)
# DGX Spark에서 실행: ./scripts/deploy.sh
# Pulls latest code, rebuilds containers, and restarts services.
# For first-time setup, use: ./scripts/setup_dgx.sh
# =============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}ML Experiment Hub - Deploy${NC}"
echo "══════════════════════════════════════════"

# ── Step 1: Pull latest code ────────────────────────────────────────────
echo -e "${GREEN}Pulling latest code...${NC}"
git pull origin lead/main

# ── Step 2: Rebuild containers ──────────────────────────────────────────
echo -e "${GREEN}Rebuilding containers...${NC}"
docker compose build

# ── Step 3: Restart services ────────────────────────────────────────────
echo -e "${GREEN}Restarting services...${NC}"
docker compose down
docker compose up -d

# ── Step 4: Wait and verify ─────────────────────────────────────────────
echo -e "${GREEN}Waiting for startup...${NC}"
sleep 5

echo -e "${GREEN}Backend logs:${NC}"
docker compose logs backend --tail 20

echo ""
echo -e "${GREEN}Health check...${NC}"
if curl -sf http://localhost:3000/api/projects | head -c 200; then
    echo ""
    echo -e "${GREEN}Deploy complete.${NC}"
else
    echo ""
    echo -e "${RED}Health check failed. Check logs:${NC}"
    echo "  docker compose logs backend --tail 30"
    exit 1
fi

echo ""
echo "══════════════════════════════════════════"
echo -e "  Dashboard: ${CYAN}http://localhost:3000${NC}"
echo -e "  API:       ${CYAN}http://localhost:8002/docs${NC}"
echo "══════════════════════════════════════════"
