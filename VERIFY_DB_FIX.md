# Database Path Fix Verification Guide

## Problem Fixed
- **Before**: Alembic created DB at `/app/ml_experiments.db` (with migrations), but app used `/data/ml_hub.db` (without migrations) → 500 errors
- **After**: Both use `/app/data/ml_hub.db` through unified `DATABASE_URL` environment variable

## Quick Verification (Docker)

### 1. Clean and Rebuild
```bash
# Remove old containers and volumes
docker compose down -v

# Rebuild and start (this will create fresh DB with migrations)
docker compose up -d --build
```

### 2. Check Logs
```bash
# Watch backend logs for migration success
docker compose logs -f backend

# Look for:
# ✅ "Running database migrations..."
# ✅ "Migrations OK"
# ✅ "Starting server..."
```

### 3. Verify Database Schema
```bash
# Connect to backend container and check DB schema
docker compose exec backend python -c "
import sqlite3
conn = sqlite3.connect('/app/data/ml_hub.db')
cols = conn.execute('PRAGMA table_info(experiment_configs)').fetchall()
col_names = [c[1] for c in cols]
print('Columns in experiment_configs:')
for col in col_names:
    print(f'  - {col}')
print(f'\n✅ project_name present: {\"project_name\" in col_names}')
conn.close()
"
```

Expected output should include:
```
Columns in experiment_configs:
  - id
  - name
  - description
  - project_name    # ← This must be present!
  - ...

✅ project_name present: True
```

### 4. Test API Endpoint
```bash
# Test experiments endpoint (should return 200, not 500)
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost:8002/api/experiments

# Or with response body:
curl http://localhost:8002/api/experiments | jq
```

Expected:
- ✅ HTTP Status: 200
- ✅ JSON response with experiments array (may be empty: `{"experiments": []}`)

### 5. Verify Database Location
```bash
# Check that DB file exists at the correct location
docker compose exec backend ls -lh /app/data/ml_hub.db

# Check that old DB files DON'T exist (or are not being used)
docker compose exec backend sh -c "
  echo 'Checking old DB paths...'
  if [ -f /app/ml_experiments.db ]; then
    echo '⚠️  WARNING: /app/ml_experiments.db still exists (should be deleted)'
  else
    echo '✅ /app/ml_experiments.db does not exist (good)'
  fi

  if [ -f /data/ml_hub.db ]; then
    echo '⚠️  WARNING: /data/ml_hub.db still exists (should be deleted)'
  else
    echo '✅ /data/ml_hub.db does not exist (good)'
  fi
"
```

## Configuration Changes Summary

| File | Change | Purpose |
|------|--------|---------|
| `backend/config.py` | `DATABASE_URL` default → `sqlite+aiosqlite:///./data/ml_hub.db` | App default path |
| `docker-compose.yml` | `DATABASE_URL=sqlite+aiosqlite:////app/data/ml_hub.db` | Override for Docker |
| `alembic.ini` | `sqlalchemy.url =` (empty) | Placeholder (overridden by env.py) |
| `alembic/env.py` | Read from `backend.config.settings` | Single source of truth |
| `backend/entrypoint.sh` | Added `mkdir -p /app/data` | Ensure directory exists |
| `backend/Dockerfile` | Added `/app/data` to mkdir | Ensure directory exists |

## Single Source of Truth Flow

```
1. docker-compose.yml sets:
   DATABASE_URL=sqlite+aiosqlite:////app/data/ml_hub.db

2. backend/config.py reads it:
   settings.DATABASE_URL (from environment or default)

3. alembic/env.py reads from backend.config:
   config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

4. Both app and alembic now use: /app/data/ml_hub.db
```

## Troubleshooting

### If migrations fail:
```bash
# Check alembic can connect
docker compose exec backend uv run alembic current

# Run migrations manually
docker compose exec backend uv run alembic upgrade head
```

### If 500 errors persist:
```bash
# Check which DB the app is actually using
docker compose exec backend python -c "
from backend.config import settings
print(f'DATABASE_URL: {settings.DATABASE_URL}')
"

# Should output: DATABASE_URL: sqlite+aiosqlite:////app/data/ml_hub.db
```

### To start fresh:
```bash
# Nuclear option: delete everything and rebuild
docker compose down -v
docker system prune -f
docker compose up -d --build
```

## Success Criteria

✅ All must be true:
1. Database created at `/app/data/ml_hub.db`
2. Alembic migrations applied successfully
3. `project_name` column exists in `experiment_configs` table
4. API returns 200 on `GET /api/experiments`
5. No old DB files at `/app/ml_experiments.db` or `/data/ml_hub.db`
6. Both app and alembic use the same database path
