# ML Experiment Hub

A generic, self-hosted platform for running, monitoring, and comparing ML training experiments.
Any model type can be integrated via the **adapter plugin interface** — classification, retrieval,
generation, or any custom task.

## Quick Start

```bash
git clone https://github.com/hyunlord/ml-experiment-hub
cd ml-experiment-hub
docker compose up -d --build
# → http://localhost:3000
```

That's it. No scripts, no `.env` file needed. Everything starts automatically:
- Backend (FastAPI + Gunicorn) on port 8002
- Frontend (React + Nginx) on port 3000
- DB migrations run on first start
- Data persists in `./data/` directory

### Code Update

```bash
git pull
docker compose up -d --build
```

### DB Reset (migration issues or fresh start)

```bash
docker compose down -v
docker compose up -d --build
```

### Optional: Mount Your Data

Create a `.env` file to point to your ML data directories:

```bash
PROJECTS_DIR=/home/nvidia/projects      # ML project source code (read-only)
DATA_DIR=/home/nvidia/data              # Training data (read-only)
CHECKPOINT_DIR=/home/nvidia/checkpoints # Checkpoint storage
```

Without `.env`, empty placeholder directories are used.

## Features

- **Adapter Plugin System** — plug in any model type via `BaseAdapter` interface
- **One-click training** — configure and launch experiments from a web UI
- **Real-time dashboard** — live loss curves, custom metrics, GPU/CPU stats via WebSocket
- **Experiment comparison** — side-by-side metric charts and config diff across runs
- **Hyperparameter search** — Optuna-based TPE with trial tracking and parameter importance
- **Dataset registry** — register datasets with auto-detect, split configuration, and previews
- **Experiment queue** — drag-and-drop queue with configurable concurrency
- **Notifications** — browser, Discord, and Slack webhook notifications
- **Search demo** — cross-modal retrieval (image ↔ text) via adapter
- **Classifier demo** — image classification inference via adapter
- **GPU auto-configure** — detects VRAM and sets optimal batch size automatically
- **Health monitoring** — OOM detection, disk space warnings, GPU temperature alerts
- **Server recovery** — survives restarts; reconnects to live processes or marks dead ones failed

## Available Adapters

| Adapter | Model Type | Metrics | Demo |
|---------|-----------|---------|------|
| `dummy_classifier` | MNIST/CIFAR-10 CNN | accuracy, precision, recall, F1 | Classifier Demo |
| `vlm_quantization` | Cross-modal hashing | mAP, retrieval metrics | Search Demo |
| `pytorch_lightning` | Any Lightning model | configurable | — |
| `huggingface` | HuggingFace Trainer | configurable | — |

**Adding a new adapter?** See [docs/new-adapter-guide.md](docs/new-adapter-guide.md).

## Architecture

```
ml-experiment-hub/
├── adapters/              # Model adapter plugins
│   ├── base.py            # BaseAdapter ABC (the interface)
│   ├── dummy_classifier/  # Example: image classification
│   └── vlm_quantization/  # Example: cross-modal hashing
├── backend/
│   ├── api/               # REST + WebSocket endpoints
│   ├── core/              # Process manager, system monitor
│   ├── models/            # SQLModel ORM (SQLite)
│   ├── services/          # Health checks, log manager, metric archiver, notifier
│   └── workers/           # Subprocess entry points (eval, index build)
├── frontend/src/          # React 18 + TypeScript + Vite + Tailwind
│   ├── api/               # API client functions
│   ├── components/        # Shared React components
│   └── pages/             # Page components (dashboard, monitor, compare, demos)
├── configs/               # Training presets (dgx_spark.yaml)
├── shared/                # Shared schemas and enums
├── scripts/               # Dev scripts (gate, setup)
├── tests/                 # Pytest test suite
└── docker-compose.yml     # Production deployment (one command)
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLModel, SQLite (WAL mode), asyncio |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Real-time | WebSocket (metric streaming + system stats) |
| Process | subprocess + asyncio (training/eval as child processes) |
| Deployment | Docker Compose, NVIDIA Container Toolkit |

## Your First Experiment

1. **Open the dashboard** at http://localhost:3000
2. **Create an experiment** — Experiments → New Experiment
3. **Select framework** — choose `dummy_classifier` for a quick test
4. **Configure** — set `{"dataset": "mnist", "epochs": 3, "learning_rate": 0.001}`
5. **Start training** — click Start, watch live metrics on the run monitor page
6. **Compare** — select experiments and click Compare for side-by-side analysis
7. **Try the demo** — go to Classifier Demo, upload an image, and classify it

## API Overview

| Endpoint | Description |
|----------|-------------|
| `GET /api/experiments` | List all experiments |
| `POST /api/experiments` | Create experiment |
| `POST /api/runs/{id}/start` | Start training run |
| `POST /api/runs/{id}/stop` | Stop training run |
| `GET /api/runs/{id}/metrics` | Get run metrics |
| `WS /api/ws/{run_id}` | Live metric + system stat stream |
| `POST /api/predict/image` | Classify image (generic, adapter-routed) |
| `POST /api/search/text` | Text search (adapter-routed) |
| `POST /api/search/image` | Image search (adapter-routed) |
| `GET /api/datasets` | List registered datasets |
| `GET /api/system/health` | Health check |
| `GET /api/system/gpu-info` | GPU info + auto-config |

Full interactive docs at `/docs` (Swagger UI) and `/redoc`.

## Stability Features

- **Server restart recovery** — on startup, checks PID liveness of in-progress runs; reconnects if alive, marks failed if dead
- **Log rotation** — training logs compressed after 7 days; stats in health endpoint
- **DB optimization** — SQLite WAL mode, composite indexes on MetricLog, metric archival for old runs
- **OOM detection** — parses "CUDA out of memory" from training output, shows clear error in UI
- **Disk space check** — warns when free space drops below 2 GB
- **GPU temperature alerts** — warning at 85°C, critical at 95°C
- **Docker memory limits** — backend capped at 4 GB to avoid competing with training

## Local Development

```bash
# 1. Clone and install
git clone <repo-url> && cd ml-experiment-hub
uv sync --all-extras
cd frontend && npm install && cd ..

# 2. Start dev servers
# Terminal 1: Backend
uv run uvicorn backend.main:app --reload --port 8002

# Terminal 2: Frontend
cd frontend && npm run dev
```

- Dashboard: http://localhost:5173
- API docs: http://localhost:8002/docs

```bash
# Run tests
uv run pytest -q

# Lint + format
uv run ruff check .
uv run ruff format .

# Full gate check (lint + test + smoke)
./scripts/gate.sh
```

## License

MIT
