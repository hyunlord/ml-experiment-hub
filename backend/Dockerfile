# =============================================================================
# ML Experiment Hub - Backend Dockerfile
# Multi-stage build: dev (hot reload) / prod (gunicorn)
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

# Copy dependency spec first for layer caching
COPY pyproject.toml ./

# Install production dependencies (no dev extras)
RUN uv pip install --system -e .

# Create runtime directories
RUN mkdir -p /data/logs /data/venvs /tmp/configs

# ---------------------------------------------------------------------------
# Stage: dev - Development with hot reload
# ---------------------------------------------------------------------------
FROM base AS dev

# Install dev dependencies too
RUN uv pip install --system -e ".[dev]"

# Source code will be bind-mounted at runtime
# Copy just enough to start (in case volumes aren't mounted)
COPY backend/ ./backend/
COPY shared/ ./shared/
COPY adapters/ ./adapters/
COPY alembic/ ./alembic/
COPY alembic.ini ./

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# Stage: prod - Production with gunicorn + uvicorn workers
# ---------------------------------------------------------------------------
FROM base AS prod

# Install gunicorn for production
RUN uv pip install --system gunicorn

# Copy application code (no volumes in prod)
COPY backend/ ./backend/
COPY shared/ ./shared/
COPY adapters/ ./adapters/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY backend/seeds/ ./backend/seeds/ 2>/dev/null || true

EXPOSE 8000

# gunicorn with uvicorn workers for async support
# - Workers: 2 * CPU + 1 (controlled via WEB_CONCURRENCY env)
# - Each worker runs uvicorn's async event loop
CMD ["gunicorn", "backend.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--timeout", "300", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-"]
