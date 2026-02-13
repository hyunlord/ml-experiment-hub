import client from './client'
import type { ConfigSchema } from '@/types/schema'

export interface ConfigSchemaListResponse {
  schemas: ConfigSchema[]
  total: number
}

export const getSchemas = async (): Promise<ConfigSchemaListResponse> => {
  const response = await client.get('/schemas')
  return response.data
}

export const getSchema = async (id: number): Promise<ConfigSchema> => {
  const response = await client.get(`/schemas/${id}`)
  return response.data
}
