import client from './client'
import type { TemplateInfo, TemplateConfigSchema } from '@/types/project'

export const getTemplates = async (): Promise<TemplateInfo[]> => {
  const response = await client.get('/templates')
  return response.data
}

export const getTemplate = async (id: string): Promise<TemplateInfo> => {
  const response = await client.get(`/templates/${id}`)
  return response.data
}

export const getTemplateSchema = async (
  id: string,
  taskId?: string
): Promise<TemplateConfigSchema> => {
  const response = await client.get(`/templates/${id}/schema`, {
    params: taskId ? { task: taskId } : undefined,
  })
  return response.data
}
