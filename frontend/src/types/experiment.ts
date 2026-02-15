export enum ExperimentStatus {
  DRAFT = 'draft',
  QUEUED = 'queued',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum RunStatus {
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export interface Experiment {
  id: number
  name: string
  description: string
  status: ExperimentStatus
  config: Record<string, unknown>
  schema_id: number | null
  project_id: number | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface ExperimentRun {
  id: number
  experiment_config_id: number
  status: RunStatus
  pid: number | null
  log_path: string | null
  metrics_summary: Record<string, unknown> | null
  checkpoint_path: string | null
  started_at: string | null
  ended_at: string | null
}

export interface MetricLog {
  id: number
  run_id: number
  step: number
  epoch: number | null
  timestamp: string
  metrics_json: Record<string, unknown>
}

export interface ExperimentCreate {
  name: string
  description?: string
  config?: Record<string, unknown>
  schema_id?: number | null
  project_id?: number | null
  base_config_path?: string | null
  tags?: string[]
}

export interface ExperimentUpdate {
  name?: string
  description?: string
  config?: Record<string, unknown>
  tags?: string[]
}

export interface ExperimentListResponse {
  experiments: Experiment[]
  total: number
}
