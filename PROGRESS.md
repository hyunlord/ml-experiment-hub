# Progress Log

## Milestone 8: System Monitor Enhancement + Multi-Server Support

### Status: COMPLETE

### Summary
Enhanced the System Monitor page with comprehensive hardware monitoring, multi-server
registration, history charts, alert thresholds, and a lightweight remote agent module.

### Tasks
| # | Task | Status |
|---|------|--------|
| 1 | Backend system info service (psutil + nvidia-smi) | DONE |
| 2 | Server model + Alembic migration + CRUD API | DONE |
| 3 | System history model + background collection service | DONE |
| 4 | Enhanced SystemPage frontend (GPU/CPU/RAM/Disk/Net/Processes) | DONE |
| 5 | Server management UI (Settings) + TopBar server selector | DONE |
| 6 | History charts (recharts, 1h/6h/24h) | DONE |
| 7 | Alert thresholds (Settings) + warning banners (SystemPage) | DONE |
| 8 | Lightweight agent module (agent/) | DONE |

### Files Created
- `backend/services/system_info.py` — Comprehensive system info collector (psutil + nvidia-smi)
- `backend/services/system_history.py` — Background history collection + downsampling service
- `backend/api/servers.py` — Server CRUD + connection test API
- `alembic/versions/430b08747772_add_servers_and_system_history.py` — DB migration
- `frontend/src/api/servers.ts` — Server API client
- `frontend/src/stores/serverStore.ts` — Zustand store for active server selection
- `agent/main.py` — Lightweight FastAPI agent for remote monitoring
- `agent/collector.py` — System info collector (standalone, no hub deps)
- `agent/requirements.txt` — Agent dependencies (fastapi, uvicorn, psutil)

### Files Modified
- `backend/api/system.py` — Added /stats (delegated to system_info), /history endpoint
- `backend/main.py` — Registered servers router, system_history service start/stop
- `backend/models/experiment.py` — Added Server + SystemHistorySnapshot models
- `frontend/src/api/system.ts` — Added getSystemStats, getSystemHistory + types
- `frontend/src/components/Layout.tsx` — TopBar server selector dropdown
- `frontend/src/pages/SettingsPage.tsx` — Servers section + alert thresholds section
- `frontend/src/pages/SystemPage.tsx` — Full rewrite with GPU cards, per-core CPU,
  RAM/Disk/Network sections, training processes, history charts, alert banners

### Key Features
- **GPU monitoring**: nvidia-smi detailed cards (utilization, memory, temp, power, fan, clock, PCIe, driver, CUDA, processes)
- **Apple Silicon support**: Detects M-series chips, shows unified memory + MPS status
- **CPU-only fallback**: Graceful "no GPU" message with link to Settings > Servers
- **Multi-server**: Register servers in Settings, select active server in TopBar dropdown
- **History charts**: CPU%, RAM%, GPU util%, GPU mem%, GPU temp over 1h/6h/24h (recharts)
- **Alert thresholds**: Configurable warn/crit thresholds for GPU temp, GPU mem, RAM, disk
- **Warning banners**: Real-time alert banners on System page when thresholds exceeded
- **Remote agent**: `python agent/main.py --port 8001` for remote system monitoring
- **Data lifecycle**: 10s collection interval, 24h raw retention, then 1-min downsampling

### Gate
- 258 tests passed, 0 failures
- Lint clean (ruff check + format)
- TypeScript clean (tsc --noEmit)
- Smoke test passed

---

## Previous Milestones

### M1-M4: Core Platform
Experiment CRUD, run orchestration, metrics, schemas, datasets, HP search (Optuna).

### M5: Queue & Notifications
Experiment queue, scheduler, Discord/Slack webhooks, browser notifications.

### M6: Search Engine Plugin Interface
Generic search adapter registry, Optuna search engine.

### M7: Adapter Plugin System
Generic model adapter registry, dummy_classifier reference adapter, adapter guide.
