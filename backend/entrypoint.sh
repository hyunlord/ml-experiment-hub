#!/bin/bash
# =============================================================================
# ML Experiment Hub - Backend Entrypoint
# Runs DB migrations then starts the server.
# =============================================================================

echo "=== ML Experiment Hub Backend ==="

# Create data directories if they don't exist
mkdir -p /data/logs /data/venvs /tmp/configs

# Run Alembic migrations (non-fatal: server starts even if migration fails)
echo "Running database migrations..."
uv run alembic upgrade head && echo "Migrations OK" \
    || echo "WARNING: Migration failed, continuing with existing schema..."

# Start gunicorn with uvicorn workers
echo "Starting server..."
exec uv run gunicorn backend.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 1 \
    --bind 0.0.0.0:8002 \
    --timeout 300 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
