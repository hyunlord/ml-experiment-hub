import client from './client'
import type {
  Experiment,
  ExperimentCreate,
  ExperimentListResponse,
  MetricPoint,
} from '@/types/experiment'

interface GetExperimentsParams {
  skip?: number
  limit?: number
  status?: string
}

export const getExperiments = async (
  params?: GetExperimentsParams
): Promise<ExperimentListResponse> => {
  const response = await client.get('/experiments', { params })
  return response.data
}

export const getExperiment = async (id: string): Promise<Experiment> => {
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
  id: string,
  data: Partial<ExperimentCreate>
): Promise<Experiment> => {
  const response = await client.put(`/experiments/${id}`, data)
  return response.data
}

export const deleteExperiment = async (id: string): Promise<void> => {
  await client.delete(`/experiments/${id}`)
}

export const startExperiment = async (id: string): Promise<Experiment> => {
  const response = await client.post(`/experiments/${id}/start`)
  return response.data
}

export const stopExperiment = async (id: string): Promise<Experiment> => {
  const response = await client.post(`/experiments/${id}/stop`)
  return response.data
}

export const getExperimentMetrics = async (
  id: string
): Promise<MetricPoint[]> => {
  const response = await client.get(`/experiments/${id}/metrics`)
  return response.data
}
