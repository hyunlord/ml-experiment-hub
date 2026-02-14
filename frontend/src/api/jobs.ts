import client from './client'

// --- Types ---

export type JobType = 'eval' | 'index_build'
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface JobResponse {
  id: number
  job_type: JobType
  run_id: number
  status: JobStatus
  progress: number
  config_json: Record<string, unknown>
  result_json: Record<string, unknown>
  error_message: string | null
  started_at: string | null
  ended_at: string | null
  created_at: string
}

export interface EvalJobRequest {
  run_id: number
  checkpoint?: string
  bit_lengths?: number[]
  k_values?: number[]
}

export interface IndexBuildJobRequest {
  run_id: number
  checkpoint?: string
  image_dir?: string | null
  captions_file?: string | null
  thumbnail_size?: number
  batch_size?: number
}

export interface SearchResult {
  rank: number
  index: number
  score: number
  thumbnail_b64: string | null
  caption: string | null
}

export interface SearchResponse {
  results: SearchResult[]
  query_hash: number[]
  search_time_ms: number
  method: string
  bit_length: number
  query?: string
}

// --- Job API ---

export const createEvalJob = async (data: EvalJobRequest): Promise<JobResponse> => {
  const response = await client.post('/jobs/eval', data)
  return response.data
}

export const createIndexBuildJob = async (data: IndexBuildJobRequest): Promise<JobResponse> => {
  const response = await client.post('/jobs/index-build', data)
  return response.data
}

export const getJob = async (jobId: number): Promise<JobResponse> => {
  const response = await client.get(`/jobs/${jobId}`)
  return response.data
}

export const listJobs = async (params?: {
  job_type?: JobType
  run_id?: number
}): Promise<JobResponse[]> => {
  const response = await client.get('/jobs', { params })
  return response.data
}

export const cancelJob = async (jobId: number): Promise<{ status: string }> => {
  const response = await client.post(`/jobs/${jobId}/cancel`)
  return response.data
}

// --- Search API ---

export const searchByText = async (params: {
  query: string
  index_path: string
  checkpoint_path: string
  bit_length?: number
  top_k?: number
  method?: string
}): Promise<SearchResponse> => {
  const formData = new FormData()
  formData.append('query', params.query)
  formData.append('index_path', params.index_path)
  formData.append('checkpoint_path', params.checkpoint_path)
  formData.append('bit_length', String(params.bit_length ?? 64))
  formData.append('top_k', String(params.top_k ?? 20))
  formData.append('method', params.method ?? 'hamming')

  const response = await client.post('/search/text', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const searchByImage = async (params: {
  image: File
  index_path: string
  checkpoint_path: string
  bit_length?: number
  top_k?: number
  method?: string
}): Promise<SearchResponse> => {
  const formData = new FormData()
  formData.append('image', params.image)
  formData.append('index_path', params.index_path)
  formData.append('checkpoint_path', params.checkpoint_path)
  formData.append('bit_length', String(params.bit_length ?? 64))
  formData.append('top_k', String(params.top_k ?? 20))
  formData.append('method', params.method ?? 'hamming')

  const response = await client.post('/search/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}
