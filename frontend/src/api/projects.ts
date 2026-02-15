import client from './client'
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectListResponse,
  ScanResponse,
  GitInfo,
  ConfigContent,
} from '@/types/project'

// --- Project CRUD ---

export const getProjects = async (params?: {
  skip?: number
  limit?: number
  status?: string
}): Promise<ProjectListResponse> => {
  const response = await client.get('/projects', { params })
  return response.data
}

export const getProject = async (id: number | string): Promise<Project> => {
  const response = await client.get(`/projects/${id}`)
  return response.data
}

export const createProject = async (data: ProjectCreate): Promise<Project> => {
  const response = await client.post('/projects', data)
  return response.data
}

export const updateProject = async (
  id: number | string,
  data: ProjectUpdate
): Promise<Project> => {
  const response = await client.put(`/projects/${id}`, data)
  return response.data
}

export const deleteProject = async (id: number | string): Promise<void> => {
  await client.delete(`/projects/${id}`)
}

// --- Scan ---

export const scanDirectory = async (path: string): Promise<ScanResponse> => {
  const response = await client.post('/projects/scan', { path })
  return response.data
}

export const rescanProject = async (id: number | string): Promise<Project> => {
  const response = await client.post(`/projects/${id}/rescan`)
  return response.data
}

// --- Git & Config ---

export const getProjectGitInfo = async (
  id: number | string
): Promise<GitInfo> => {
  const response = await client.get(`/projects/${id}/git`)
  return response.data
}

export const getConfigContent = async (
  projectId: number | string,
  configPath: string
): Promise<ConfigContent> => {
  const response = await client.get(
    `/projects/${projectId}/configs/${configPath}`
  )
  return response.data
}
