# ML Experiment Hub

A self-hosted platform for running, monitoring, and comparing ML training experiments on NVIDIA GPUs. Built for the **vlm_quantization** (cross-modal deep hashing) project, but extensible to any PyTorch Lightning workflow.

## Features

- **One-click training** — configure and launch experiments from a web UI
- **Real-time dashboard** — live loss curves, retrieval metrics, GPU/CPU stats via WebSocket
- **Experiment comparison** — side-by-side metric tables across runs
- **GPU auto-configure** — detects VRAM and sets optimal batch size automatically
- **Evaluation jobs** — run mAP evaluation on saved checkpoints
- **Search demo** — visual cross-modal retrieval (image ↔ text) from trained models
- **Dataset management** — register, preview, and prepare JSONL datasets
- **Health monitoring** — OOM detection, disk space warnings, GPU temperature alerts
- **Server recovery** — survives restarts; reconnects to live processes or marks dead ones failed

## Architecture

```
ml-experiment-hub/
├── backend/            # FastAPI async server
│   ├── api/            # REST + WebSocket endpoints
│   ├── core/           # Process manager, system monitor
│   ├── models/         # SQLModel ORM (SQLite)
│   ├── services/       # Health checks, log manager, metric archiver
│   └── workers/        # Subprocess entry points (eval, index build)
├── frontend/           # React 18 + TypeScript + Vite + Tailwind
├── adapters/           # ML framework adapters
│   ├── base.py         # BaseAdapter interface
│   ├── pytorch_lightning.py
│   └── vlm_quantization/
├── configs/            # Training presets (dgx_spark.yaml)
├── shared/             # Shared schemas and enums
├── scripts/            # Setup, deploy, gate scripts
├── tests/              # Pytest test suite
└── docker-compose.yml  # Production deployment
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLModel, SQLite (WAL mode), asyncio |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Real-time | WebSocket (metric streaming + system stats) |
| Process | subprocess + asyncio (training/eval as child processes) |
| Deployment | Docker Compose, NVIDIA Container Toolkit |

## Quick Start

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js 18+
- Docker + Docker Compose (for production)
- NVIDIA GPU + drivers (optional for local dev)

### Local Development

```bash
# 1. Clone and setup
git clone <repo-url> && cd ml-experiment-hub
./scripts/setup.sh

# 2. Start dev servers
./scripts/dev.sh
# Backend: http://localhost:8000  (API docs: /docs)
# Frontend: http://localhost:5173
```

### Docker (Production)

```bash
# Set data paths
export DATA_DIR=~/data          # COCO, JSONL datasets
export CHECKPOINT_DIR=~/checkpoints
export PROJECTS_DIR=~/projects  # vlm_quantization source

# Build and start
docker compose up -d --build

# Dashboard: http://localhost:3000
# API docs:  http://localhost:8000/docs
```

## DGX Spark Setup

For NVIDIA DGX Spark (GB10 Grace-Blackwell, 128 GB unified memory):

```bash
# One-time setup (checks GPU, Docker, creates .env, builds images)
./scripts/setup_dgx.sh --data-dir ~/data --checkpoint-dir ~/checkpoints

# Start
docker compose up -d

# Open dashboard
open http://localhost:3000
```

See `configs/dgx_spark.yaml` for the pre-tuned training preset (SigLIP2 backbone, BF16, auto batch size).

## Running Your First Experiment

1. **Open the dashboard** at `http://localhost:3000`
2. **Create an experiment** — click "New Experiment", fill in a name
3. **Configure training** — select backbone, dataset, batch size (or "auto")
4. **Start training** — click "Start". Watch live metrics on the dashboard.
5. **Compare results** — go to the Comparison page to see metrics across runs
6. **Run evaluation** — select a checkpoint and launch an eval job
7. **Try search** — go to the Search Demo page, type a query or upload an image

## API Overview

| Endpoint | Description |
|----------|-------------|
| `GET /api/experiments` | List all experiments |
| `POST /api/experiments` | Create experiment |
| `POST /api/runs/{id}/start` | Start training run |
| `POST /api/runs/{id}/stop` | Stop training run |
| `GET /api/runs/{id}/metrics` | Get run metrics |
| `WS /api/ws/{run_id}` | Live metric + system stat stream |
| `GET /api/system/gpu-info` | GPU info + auto-config preview |
| `GET /api/system/health` | Health check (DB, disk, logs) |
| `POST /api/jobs` | Launch eval/index-build job |
| `GET /api/search` | Cross-modal search query |
| `GET /api/datasets` | List registered datasets |
| `POST /api/datasets/{id}/prepare` | Prepare dataset JSONL |
| `GET /api/compare` | Compare metrics across runs |

Full interactive docs at `/docs` (Swagger UI) and `/redoc`.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./ml_experiments.db` | Database connection |
| `PROJECTS_DIR` | `./projects` | ML project source code |
| `DATA_DIR` | `./data` | Training data (COCO, JSONL) |
| `CHECKPOINT_BASE_DIR` | `./checkpoints` | Model checkpoints |
| `LOG_DIR` | `./logs` | Training logs |
| `VENVS_DIR` | `/data/venvs` | Per-project Python venvs |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |

### Training Presets

Pre-configured YAML files in `configs/`:

- **`dgx_spark.yaml`** — DGX Spark (GB10): SigLIP2, BF16, auto batch size, 30 epochs

## Stability Features

- **Server restart recovery** — on startup, checks PID liveness of in-progress runs; reconnects if alive, marks failed if dead
- **Log rotation** — training logs compressed after 7 days; log directory stats in health endpoint
- **DB optimization** — SQLite WAL mode, composite indexes on MetricLog, automatic metric archival for old runs
- **OOM detection** — parses "CUDA out of memory" from training output, broadcasts error via WebSocket
- **Disk space check** — warns when free space drops below 2 GB
- **GPU temperature alerts** — warning at 85 C, critical at 95 C
- **Docker memory limits** — backend capped at 4 GB to avoid competing with training processes

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run gate check (lint + typecheck + tests)
./scripts/gate.sh

# Format code
uv run ruff format .
uv run ruff check --fix .
```

## License

MIT
