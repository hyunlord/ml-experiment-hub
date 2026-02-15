import client from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Server {
  id: number
  name: string
  host: string
  port: number
  auth_type: string
  api_key: string
  description: string
  tags: string[]
  is_default: boolean
  is_local: boolean
  created_at: string
  updated_at: string
}

export interface ServerCreate {
  name: string
  host: string
  port?: number
  auth_type?: string
  api_key?: string
  description?: string
  tags?: string[]
  is_default?: boolean
  is_local?: boolean
}

export interface ServerUpdate {
  name?: string
  host?: string
  port?: number
  auth_type?: string
  api_key?: string
  description?: string
  tags?: string[]
  is_default?: boolean
}

export interface ConnectionTestResult {
  ok: boolean
  latency_ms: number | null
  error: string | null
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export async function listServers(): Promise<Server[]> {
  const res = await client.get('/servers')
  return res.data
}

export async function getServer(id: number): Promise<Server> {
  const res = await client.get(`/servers/${id}`)
  return res.data
}

export async function createServer(data: ServerCreate): Promise<Server> {
  const res = await client.post('/servers', data)
  return res.data
}

export async function updateServer(id: number, data: ServerUpdate): Promise<Server> {
  const res = await client.put(`/servers/${id}`, data)
  return res.data
}

export async function deleteServer(id: number): Promise<void> {
  await client.delete(`/servers/${id}`)
}

export async function testServerConnection(id: number): Promise<ConnectionTestResult> {
  const res = await client.post(`/servers/${id}/test`)
  return res.data
}
