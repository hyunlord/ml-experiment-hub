/** Metric message from WebSocket /ws/runs/{runId}/metrics */
export interface MetricMessage {
  type: 'metric'
  run_id: number
  step: number
  epoch: number | null
  metrics: Record<string, number>
  timestamp: string
}

/** System stats from WebSocket /ws/runs/{runId}/system */
export interface SystemMessage {
  type: 'system_stats'
  run_id: number
  timestamp: string
  gpus?: GpuInfo[]
  gpu_util?: number | null
  gpu_memory_used?: number | null
  gpu_memory_total?: number | null
  cpu_percent?: number | null
  ram_percent?: number | null
  cpu?: { percent: number; count: number }
  ram?: { used_gb: number; total_gb: number; percent: number }
}

export interface GpuInfo {
  index: number
  name: string
  util: number
  memory_used_mb: number
  memory_total_mb: number
  memory_percent: number
  temperature: number | null
}

/** Log line from WebSocket /ws/runs/{runId}/logs */
export interface LogMessage {
  type: 'log'
  run_id: number
  line: string
}

/** Hash analysis detail (non-scalar data) from metrics channel */
export interface HashAnalysisDetailMessage {
  type: 'hash_analysis_detail'
  run_id: number
  step: number
  epoch: number | null
  samples: HashSample[]
}

export interface HashSample {
  /** Base64-encoded JPEG thumbnail (128x128) */
  thumbnail: string
  /** Binary hash code as array of 0/1 */
  code: number[]
}
