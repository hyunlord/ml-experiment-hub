# ML Experiment Hub

A platform for managing, running, and monitoring machine learning experiments.

## Architecture

```
ml-experiment-hub/
├── backend/          # FastAPI server
│   ├── api/          # REST + WebSocket endpoints
│   ├── core/         # Experiment execution engine, process management
│   ├── models/       # DB models (SQLModel)
│   ├── schemas/      # Pydantic request/response schemas
│   └── services/     # Business logic
├── frontend/         # React (Vite + TypeScript)
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       ├── stores/   # Zustand state management
│       └── api/      # API client
├── adapters/         # ML framework adapters (PyTorch Lightning, HuggingFace)
├── shared/           # Shared types and config schemas
├── pyproject.toml    # Python dependencies
└── docker-compose.yml
```

## Tech Stack

- **Backend**: FastAPI + SQLModel + SQLite (dev) / PostgreSQL (production)
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS
- **State Management**: Zustand
- **Real-time**: WebSocket (training metric streaming)
- **Process Management**: subprocess + asyncio

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm or pnpm

### Backend Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -e ".[dev]"

# Start the server
uvicorn backend.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

The frontend dev server runs on `http://localhost:5173` and proxies API requests to the backend at `http://localhost:8000`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/experiments` | List experiments |
| POST | `/experiments` | Create experiment |
| GET | `/experiments/{id}` | Get experiment detail |
| PUT | `/experiments/{id}` | Update experiment |
| DELETE | `/experiments/{id}` | Delete experiment |
| POST | `/experiments/{id}/start` | Start experiment |
| POST | `/experiments/{id}/stop` | Stop experiment |
| GET | `/experiments/{id}/metrics` | Get metrics |
| WS | `/ws/experiments/{id}/metrics` | Stream metrics (WebSocket) |

## ML Framework Adapters

The platform supports extensible ML framework adapters:

- **PyTorch Lightning**: Training with Lightning callbacks for metric reporting
- **HuggingFace Transformers**: Training with HuggingFace Trainer integration

Adapters implement the `BaseAdapter` interface defined in `adapters/base.py`.
