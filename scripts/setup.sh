#!/usr/bin/env bash
# Initial project setup script.
# Usage: ./scripts/setup.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}ML Experiment Hub - Setup${NC}"
echo "══════════════════════════════════════════"

# ── 1. Backend dependencies ──────────────────────────────────────────────
echo -e "\n${GREEN}[1/5]${NC} Installing backend dependencies..."
if ! command -v uv &>/dev/null; then
    echo -e "${RED}Error: uv is not installed. Install it: https://docs.astral.sh/uv/${NC}"
    exit 1
fi
uv sync
echo -e "${GREEN}  ✓ Backend dependencies installed${NC}"

# ── 2. Frontend dependencies ─────────────────────────────────────────────
echo -e "\n${GREEN}[2/5]${NC} Installing frontend dependencies..."
cd frontend && npm install && cd "$ROOT_DIR"
echo -e "${GREEN}  ✓ Frontend dependencies installed${NC}"

# ── 3. Environment file ──────────────────────────────────────────────────
echo -e "\n${GREEN}[3/5]${NC} Checking environment file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${YELLOW}  ✓ Created .env from .env.example — review and update paths${NC}"
else
    echo -e "${GREEN}  ✓ .env already exists${NC}"
fi

# ── 4. Database migration ────────────────────────────────────────────────
echo -e "\n${GREEN}[4/5]${NC} Running database migrations..."
uv run alembic upgrade head
echo -e "${GREEN}  ✓ Database migrated${NC}"

# ── 5. Seed default schemas ──────────────────────────────────────────────
echo -e "\n${GREEN}[5/5]${NC} Seeding default config schemas..."
uv run python -m backend.seeds.vlm_quantization
echo -e "${GREEN}  ✓ Config schemas seeded${NC}"

echo -e "\n══════════════════════════════════════════"
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "  ./scripts/dev.sh          # Start local dev servers"
echo "  docker compose up --build # Start with Docker"
