import { create } from 'zustand'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MetricPoint {
  step: number
  value: number
}

interface RunMetrics {
  /** Raw metric timeseries keyed by metric name. */
  series: Map<string, MetricPoint[]>
  /** Latest value for each metric key. */
  latest: Record<string, number>
  /** All known metric keys for this run. */
  keys: Set<string>
}

interface MetricsState {
  /** Per-run metrics cache. */
  runs: Map<string | number, RunMetrics>

  // -- Actions --

  /** Ingest a metric message from WebSocket. */
  ingest: (msg: {
    run_id: number | string
    step: number
    metrics: Record<string, number>
  }) => void

  /** Get timeseries for a specific metric key. */
  getMetricSeries: (runId: number | string, key: string) => MetricPoint[]

  /** Get all available metric keys for a run. */
  getAvailableKeys: (runId: number | string) => string[]

  /** Get latest values for all metrics of a run. */
  latestMetrics: (runId: number | string) => Record<string, number>

  /** Clear all data for a run. */
  clearRun: (runId: number | string) => void

  /** Clear everything. */
  clearAll: () => void
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum points per series before LTTB downsampling kicks in. */
const MAX_POINTS = 10_000

/** Target point count after downsampling. */
const DOWNSAMPLE_TARGET = 5_000

// ---------------------------------------------------------------------------
// LTTB (Largest-Triangle-Three-Buckets) downsampling
// ---------------------------------------------------------------------------

function lttbDownsample(data: MetricPoint[], target: number): MetricPoint[] {
  if (data.length <= target) return data

  const out: MetricPoint[] = [data[0]] // always keep first
  const bucketSize = (data.length - 2) / (target - 2)

  let prevIndex = 0

  for (let i = 1; i < target - 1; i++) {
    const bucketStart = Math.floor((i - 1) * bucketSize) + 1
    const bucketEnd = Math.min(Math.floor(i * bucketSize) + 1, data.length - 1)

    // Next bucket average (for area calculation)
    const nextBucketStart = Math.floor(i * bucketSize) + 1
    const nextBucketEnd = Math.min(
      Math.floor((i + 1) * bucketSize) + 1,
      data.length - 1,
    )

    let avgStep = 0
    let avgVal = 0
    let nextCount = 0
    for (let j = nextBucketStart; j < nextBucketEnd; j++) {
      avgStep += data[j].step
      avgVal += data[j].value
      nextCount++
    }
    if (nextCount > 0) {
      avgStep /= nextCount
      avgVal /= nextCount
    }

    // Find point in current bucket with largest triangle area
    let maxArea = -1
    let maxIdx = bucketStart

    const prev = data[prevIndex]

    for (let j = bucketStart; j < bucketEnd; j++) {
      const area = Math.abs(
        (prev.step - avgStep) * (data[j].value - prev.value) -
          (prev.step - data[j].step) * (avgVal - prev.value),
      )
      if (area > maxArea) {
        maxArea = area
        maxIdx = j
      }
    }

    out.push(data[maxIdx])
    prevIndex = maxIdx
  }

  out.push(data[data.length - 1]) // always keep last
  return out
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

function getOrCreateRun(
  runs: Map<string | number, RunMetrics>,
  runId: string | number,
): RunMetrics {
  let run = runs.get(runId)
  if (!run) {
    run = { series: new Map(), latest: {}, keys: new Set() }
    runs.set(runId, run)
  }
  return run
}

export const useMetricsStore = create<MetricsState>((set, get) => ({
  runs: new Map(),

  ingest: (msg) => {
    set((state) => {
      // Shallow-clone the runs map for immutability
      const runs = new Map(state.runs)
      const run = getOrCreateRun(runs, msg.run_id)

      // Clone latest and keys
      const latest = { ...run.latest }
      const keys = new Set(run.keys)
      const series = new Map(run.series)

      for (const [key, value] of Object.entries(msg.metrics)) {
        if (value == null || !Number.isFinite(value)) continue

        latest[key] = value
        keys.add(key)

        // Append to series
        let pts = series.get(key)
        if (!pts) {
          pts = []
          series.set(key, pts)
        }

        // Avoid duplicate steps (take latest value)
        if (pts.length > 0 && pts[pts.length - 1].step === msg.step) {
          pts[pts.length - 1] = { step: msg.step, value }
        } else {
          pts.push({ step: msg.step, value })
        }

        // Downsample if over limit
        if (pts.length > MAX_POINTS) {
          series.set(key, lttbDownsample(pts, DOWNSAMPLE_TARGET))
        }
      }

      runs.set(msg.run_id, { series, latest, keys })
      return { runs }
    })
  },

  getMetricSeries: (runId, key) => {
    const run = get().runs.get(runId)
    return run?.series.get(key) ?? []
  },

  getAvailableKeys: (runId) => {
    const run = get().runs.get(runId)
    return run ? Array.from(run.keys).sort() : []
  },

  latestMetrics: (runId) => {
    const run = get().runs.get(runId)
    return run?.latest ?? {}
  },

  clearRun: (runId) => {
    set((state) => {
      const runs = new Map(state.runs)
      runs.delete(runId)
      return { runs }
    })
  },

  clearAll: () => {
    set({ runs: new Map() })
  },
}))
