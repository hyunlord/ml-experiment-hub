#!/usr/bin/env bash
# =============================================================================
# DGX Spark one-click deployment script
# Usage: ./scripts/deploy.sh
# =============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}ML Experiment Hub - Docker Deployment${NC}"
echo "══════════════════════════════════════════"

# ── Step 1: Check .env ────────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo -e "${YELLOW}No .env file found. Creating from .env.example...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${RED}Please edit .env and set your paths, then re-run.${NC}"
        echo "  PROJECTS_DIR  - ML project repos (e.g., /home/nvidia/vlm_quantization)"
        echo "  DATA_DIR      - Training data (e.g., /home/nvidia/data)"
        echo "  CHECKPOINT_DIR - Checkpoint storage"
        exit 1
    else
        echo -e "${RED}.env.example not found either. Cannot proceed.${NC}"
        exit 1
    fi
fi

# Source .env for validation
set -a
source .env
set +a

# Validate required paths
for var in PROJECTS_DIR DATA_DIR CHECKPOINT_DIR; do
    val="${!var:-}"
    if [ -z "$val" ] || [ "$val" = "/home/user/projects" ] || [ "$val" = "/home/user/data" ] || [ "$val" = "/home/user/checkpoints" ]; then
        echo -e "${RED}Error: $var is not set or still has placeholder value in .env${NC}"
        exit 1
    fi
    if [ ! -d "$val" ]; then
        echo -e "${YELLOW}Warning: $var=$val does not exist. Creating...${NC}"
        mkdir -p "$val"
    fi
done

# ── Step 2: Check Docker ─────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo -e "${RED}Error: Docker Compose V2 is not available.${NC}"
    echo "Install: https://docs.docker.com/compose/install/"
    exit 1
fi

# ── Step 3: Check NVIDIA Container Toolkit ────────────────────────────────
echo -e "${GREEN}Checking NVIDIA GPU support...${NC}"
if docker info 2>/dev/null | grep -qi "nvidia\|gpu"; then
    echo -e "  ${GREEN}NVIDIA runtime detected${NC}"
elif command -v nvidia-smi &>/dev/null; then
    echo -e "  ${YELLOW}nvidia-smi found on host, but Docker NVIDIA runtime not detected.${NC}"
    echo -e "  ${YELLOW}GPU passthrough may not work. Install NVIDIA Container Toolkit:${NC}"
    echo "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/"
    read -rp "Continue anyway? [y/N] " choice
    [ "$choice" = "y" ] || [ "$choice" = "Y" ] || exit 1
else
    echo -e "  ${YELLOW}No NVIDIA GPU detected. Training will use CPU only.${NC}"
fi

# ── Step 4: Create data directories ───────────────────────────────────────
mkdir -p data/logs
mkdir -p /tmp/ml-hub-configs

# ── Step 5: Build & Run ──────────────────────────────────────────────────
echo ""
echo -e "${GREEN}Building containers...${NC}"
docker compose build

echo ""
echo -e "${GREEN}Starting services...${NC}"
docker compose up -d

echo ""
echo "══════════════════════════════════════════"
echo -e "${GREEN}ML Experiment Hub is running!${NC}"
echo ""
echo -e "  Dashboard:  ${CYAN}http://localhost:3000${NC}"
echo -e "  API:        ${CYAN}http://localhost:8002${NC}"
echo ""
echo -e "  Logs:       docker compose logs -f"
echo -e "  Stop:       docker compose down"
echo "══════════════════════════════════════════"
