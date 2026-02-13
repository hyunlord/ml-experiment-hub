import { create } from 'zustand'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GpuSnapshot {
  index: number
  name: string
  util: number
  memoryUsedMb: number
  memoryTotalMb: number
  memoryPercent: number
  temperature: number | null
}

export interface SystemSnapshot {
  timestamp: number
  gpus: GpuSnapshot[]
  cpuPercent: number
  ramPercent: number
  ramUsedGb: number | null
  ramTotalGb: number | null
}

interface SystemState {
  /** Latest snapshot per run_id. */
  current: Map<string | number, SystemSnapshot | null>
  /** Ring buffer of last 5 minutes of snapshots per run_id. */
  history: Map<string | number, SystemSnapshot[]>

  // -- Actions --

  /** Ingest a system_stats WebSocket message. */
  ingest: (msg: {
    run_id: number | string
    timestamp: string
    gpus?: Array<{
      index: number
      name: string
      util: number
      memory_used_mb: number
      memory_total_mb: number
      memory_percent: number
      temperature: number | null
    }>
    gpu_util?: number | null
    gpu_memory_used?: number | null
    gpu_memory_total?: number | null
    cpu_percent?: number | null
    ram_percent?: number | null
    cpu?: { percent: number; count: number }
    ram?: { used_gb: number; total_gb: number; percent: number }
  }) => void

  /** Get current system snapshot for a run. */
  getCurrent: (runId: number | string) => SystemSnapshot | null

  /** Get last 5 minutes of history for a run. */
  getHistory: (runId: number | string) => SystemSnapshot[]

  /** Clear data for a run. */
  clearRun: (runId: number | string) => void

  /** Clear everything. */
  clearAll: () => void
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Keep 5 minutes of history. */
const HISTORY_WINDOW_MS = 5 * 60 * 1000

/** Maximum entries in ring buffer (assuming ~1 msg/sec → 300 entries). */
const MAX_HISTORY = 600

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useSystemStore = create<SystemState>((set, get) => ({
  current: new Map(),
  history: new Map(),

  ingest: (msg) => {
    const ts = new Date(msg.timestamp).getTime()

    // Normalize GPU data
    const gpus: GpuSnapshot[] = msg.gpus
      ? msg.gpus.map((g) => ({
          index: g.index,
          name: g.name,
          util: g.util,
          memoryUsedMb: g.memory_used_mb,
          memoryTotalMb: g.memory_total_mb,
          memoryPercent: g.memory_percent,
          temperature: g.temperature,
        }))
      : msg.gpu_util != null
        ? [{
            index: 0,
            name: 'GPU 0',
            util: msg.gpu_util ?? 0,
            memoryUsedMb: msg.gpu_memory_used ?? 0,
            memoryTotalMb: msg.gpu_memory_total ?? 0,
            memoryPercent:
              msg.gpu_memory_used != null && msg.gpu_memory_total != null && msg.gpu_memory_total > 0
                ? Math.round((msg.gpu_memory_used / msg.gpu_memory_total) * 100)
                : 0,
            temperature: null,
          }]
        : []

    const snapshot: SystemSnapshot = {
      timestamp: ts,
      gpus,
      cpuPercent: msg.cpu_percent ?? msg.cpu?.percent ?? 0,
      ramPercent: msg.ram_percent ?? msg.ram?.percent ?? 0,
      ramUsedGb: msg.ram?.used_gb ?? null,
      ramTotalGb: msg.ram?.total_gb ?? null,
    }

    set((state) => {
      const current = new Map(state.current)
      const history = new Map(state.history)

      current.set(msg.run_id, snapshot)

      // Ring buffer: append + prune old entries
      const buf = [...(history.get(msg.run_id) ?? []), snapshot]
      const cutoff = ts - HISTORY_WINDOW_MS

      // Find first entry within window
      let startIdx = 0
      while (startIdx < buf.length && buf[startIdx].timestamp < cutoff) {
        startIdx++
      }

      // Slice and cap at MAX_HISTORY
      const pruned = buf.slice(startIdx)
      history.set(
        msg.run_id,
        pruned.length > MAX_HISTORY
          ? pruned.slice(pruned.length - MAX_HISTORY)
          : pruned,
      )

      return { current, history }
    })
  },

  getCurrent: (runId) => {
    return get().current.get(runId) ?? null
  },

  getHistory: (runId) => {
    return get().history.get(runId) ?? []
  },

  clearRun: (runId) => {
    set((state) => {
      const current = new Map(state.current)
      const history = new Map(state.history)
      current.delete(runId)
      history.delete(runId)
      return { current, history }
    })
  },

  clearAll: () => {
    set({ current: new Map(), history: new Map() })
  },
}))
