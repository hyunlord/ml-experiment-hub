#!/bin/bash
# =============================================================================
# ML Experiment Hub - Backend Entrypoint
# Runs DB migrations then starts the server.
# =============================================================================

echo "=== ML Experiment Hub Backend ==="

# Create data directories if they don't exist
mkdir -p /app/data /data/logs /data/venvs /tmp/configs

# Run Alembic migrations (non-fatal: server starts even if migration fails)
echo "Running database migrations..."
uv run alembic upgrade head && echo "Migrations OK" \
    || echo "WARNING: Migration failed, continuing with existing schema..."

# Start uvicorn directly (better error output than gunicorn during development)
echo "Starting server..."
exec uv run uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8002 \
    --log-level info \
    --timeout-keep-alive 300
