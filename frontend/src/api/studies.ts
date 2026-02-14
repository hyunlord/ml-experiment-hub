import client from './client'

// --- Types ---

export type TrialStatus = 'running' | 'completed' | 'pruned' | 'failed'
export type StudyStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface SearchSpaceParam {
  type: 'float' | 'int' | 'categorical'
  low?: number
  high?: number
  step?: number
  log?: boolean
  choices?: unknown[]
}

export interface TrialResult {
  id: number
  study_id: number
  trial_number: number
  params_json: Record<string, unknown>
  objective_value: number | null
  status: TrialStatus
  duration_seconds: number | null
  intermediate_values_json: Record<string, number>
  created_at: string
}

export interface StudyResponse {
  id: number
  name: string
  config_schema_id: number | null
  base_config_json: Record<string, unknown>
  search_space_json: Record<string, SearchSpaceParam>
  n_trials: number
  search_epochs: number
  subset_ratio: number
  pruner: string
  objective_metric: string
  direction: string
  status: StudyStatus
  best_trial_number: number | null
  best_value: number | null
  job_id: number | null
  created_at: string
  completed_at: string | null
  trials: TrialResult[]
}

export interface StudySummary {
  id: number
  name: string
  n_trials: number
  status: StudyStatus
  best_trial_number: number | null
  best_value: number | null
  objective_metric: string
  direction: string
  created_at: string
  completed_at: string | null
}

export interface CreateStudyRequest {
  name: string
  config_schema_id?: number | null
  base_config_json: Record<string, unknown>
  search_space_json: Record<string, SearchSpaceParam>
  n_trials?: number
  search_epochs?: number
  subset_ratio?: number
  pruner?: string
  objective_metric?: string
  direction?: string
}

export interface ParamImportance {
  importances: Record<string, number>
}

// --- API ---

export const createStudy = async (data: CreateStudyRequest): Promise<StudyResponse> => {
  const response = await client.post('/studies', data)
  return response.data
}

export const listStudies = async (): Promise<StudySummary[]> => {
  const response = await client.get('/studies')
  return response.data
}

export const getStudy = async (studyId: number): Promise<StudyResponse> => {
  const response = await client.get(`/studies/${studyId}`)
  return response.data
}

export const startStudy = async (studyId: number): Promise<StudyResponse> => {
  const response = await client.post(`/studies/${studyId}/start`)
  return response.data
}

export const cancelStudy = async (studyId: number): Promise<{ status: string }> => {
  const response = await client.post(`/studies/${studyId}/cancel`)
  return response.data
}

export const getTrials = async (studyId: number): Promise<TrialResult[]> => {
  const response = await client.get(`/studies/${studyId}/trials`)
  return response.data
}

export const getParamImportance = async (studyId: number): Promise<ParamImportance> => {
  const response = await client.get(`/studies/${studyId}/param-importance`)
  return response.data
}

export const createExperimentFromTrial = async (
  studyId: number,
  data: { trial_id?: number; name?: string; tags?: string[] }
): Promise<{ experiment_id: number; name: string; config: Record<string, unknown> }> => {
  const response = await client.post(`/studies/${studyId}/create-experiment`, data)
  return response.data
}
