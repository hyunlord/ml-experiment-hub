export enum ExperimentStatus {
  PENDING = 'PENDING',
  RUNNING = 'RUNNING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  CANCELLED = 'CANCELLED',
}

export interface Experiment {
  id: number
  name: string
  description: string
  framework: string
  status: ExperimentStatus
  script_path: string
  hyperparameters: Record<string, unknown>
  tags: string[]
  created_at: string
  updated_at: string
  started_at?: string
  completed_at?: string
}

export interface MetricPoint {
  id: number
  experiment_id: number
  step: number
  name: string
  value: number
  timestamp: string
}

export interface ExperimentCreate {
  name: string
  description?: string
  framework: string
  script_path: string
  hyperparameters: Record<string, unknown>
  tags?: string[]
}

export interface ExperimentListResponse {
  experiments: Experiment[]
  total: number
}
