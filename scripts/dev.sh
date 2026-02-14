#!/usr/bin/env bash
# Local development script - runs backend and frontend concurrently without Docker.
# Usage: ./scripts/dev.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    # Kill all background processes in this process group
    kill 0 2>/dev/null || true
    wait 2>/dev/null || true
    echo -e "${GREEN}All services stopped.${NC}"
}
trap cleanup EXIT INT TERM

# Check prerequisites
if ! command -v uv &>/dev/null; then
    echo -e "${RED}Error: uv is not installed. Install it: https://docs.astral.sh/uv/${NC}"
    exit 1
fi

if ! command -v node &>/dev/null; then
    echo -e "${RED}Error: node is not installed.${NC}"
    exit 1
fi

# Load .env if it exists
if [ -f .env ]; then
    echo -e "${GREEN}Loading .env${NC}"
    set -a
    source .env
    set +a
fi

echo -e "${GREEN}Starting ML Experiment Hub (local dev)${NC}"
echo "──────────────────────────────────────────"

# Start backend
echo -e "${GREEN}[backend]${NC} uvicorn on :8002"
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8002 2>&1 | sed "s/^/[backend] /" &

# Start frontend
echo -e "${GREEN}[frontend]${NC} vite on :5173"
cd frontend && npm run dev 2>&1 | sed "s/^/[frontend] /" &

echo "──────────────────────────────────────────"
echo -e "${GREEN}Backend:${NC}  http://localhost:8002"
echo -e "${GREEN}Frontend:${NC} http://localhost:5173"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo "──────────────────────────────────────────"

# Wait for any background process to exit
wait
