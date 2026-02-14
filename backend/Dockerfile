# =============================================================================
# ML Experiment Hub - Backend Dockerfile
# Multi-stage build: dev (hot reload) / prod (gunicorn)
# Uses uv for deterministic dependency resolution via uv.lock
# =============================================================================

# ---------------------------------------------------------------------------
# Stage: base - Common setup for all stages
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# System deps for pynvml (GPU monitoring) and general build
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specs first for layer caching
COPY pyproject.toml uv.lock ./

# Create venv and install production dependencies from lockfile
RUN uv sync --frozen --no-dev --no-install-project

# Create runtime directories
RUN mkdir -p /data/logs /data/venvs /tmp/configs

# ---------------------------------------------------------------------------
# Stage: dev - Development with hot reload
# ---------------------------------------------------------------------------
FROM base AS dev

# Install dev dependencies too
RUN uv sync --frozen --no-install-project

# Source code will be bind-mounted at runtime
# Copy just enough to start (in case volumes aren't mounted)
COPY backend/ ./backend/
COPY shared/ ./shared/
COPY adapters/ ./adapters/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Install project itself (editable)
RUN uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# Stage: prod - Production with gunicorn + uvicorn workers
# ---------------------------------------------------------------------------
FROM base AS prod

# Install gunicorn into the venv
RUN uv pip install gunicorn

# Copy application code (no volumes in prod)
COPY backend/ ./backend/
COPY shared/ ./shared/
COPY adapters/ ./adapters/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Install project itself
RUN uv sync --frozen --no-dev

EXPOSE 8000

# gunicorn with uvicorn workers for async support
CMD ["uv", "run", "gunicorn", "backend.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--timeout", "300", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-"]
