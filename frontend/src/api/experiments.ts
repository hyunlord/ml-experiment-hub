import client from './client'
import type {
  Experiment,
  ExperimentCreate,
  ExperimentUpdate,
  ExperimentListResponse,
  ExperimentRun,
  MetricLog,
} from '@/types/experiment'

interface GetExperimentsParams {
  skip?: number
  limit?: number
  status?: string
  schema_id?: number
}

// --- Experiment CRUD ---

export const getExperiments = async (
  params?: GetExperimentsParams
): Promise<ExperimentListResponse> => {
  const response = await client.get('/experiments', { params })
  return response.data
}

export const getExperiment = async (id: number | string): Promise<Experiment> => {
  const response = await client.get(`/experiments/${id}`)
  return response.data
}

export const createExperiment = async (
  data: ExperimentCreate
): Promise<Experiment> => {
  const response = await client.post('/experiments', data)
  return response.data
}

export const updateExperiment = async (
  id: number | string,
  data: ExperimentUpdate
): Promise<Experiment> => {
  const response = await client.put(`/experiments/${id}`, data)
  return response.data
}

export const deleteExperiment = async (id: number | string): Promise<void> => {
  await client.delete(`/experiments/${id}`)
}

export const cloneExperiment = async (
  id: number | string
): Promise<Experiment> => {
  const response = await client.post(`/experiments/${id}/clone`)
  return response.data
}

// --- Run management ---

export const startRun = async (
  experimentId: number | string
): Promise<ExperimentRun> => {
  const response = await client.post(`/experiments/${experimentId}/runs`)
  return response.data
}

export const stopRun = async (
  runId: number | string
): Promise<{ status: string }> => {
  const response = await client.post(`/runs/${runId}/stop`)
  return response.data
}

export const getRun = async (
  runId: number | string
): Promise<ExperimentRun> => {
  const response = await client.get(`/runs/${runId}`)
  return response.data
}

export const getExperimentRuns = async (
  experimentId: number | string
): Promise<ExperimentRun[]> => {
  const response = await client.get(`/experiments/${experimentId}/runs`)
  return response.data
}

export const getRunMetrics = async (
  runId: number | string,
  params?: { step_from?: number; step_to?: number }
): Promise<MetricLog[]> => {
  const response = await client.get(`/runs/${runId}/metrics`, { params })
  return response.data
}
