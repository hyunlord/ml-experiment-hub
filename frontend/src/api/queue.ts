import axios from 'axios'

const API = axios.create({ baseURL: 'http://localhost:8002' })

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface QueueEntry {
  id: number
  experiment_config_id: number
  experiment_name: string
  position: number
  status: 'waiting' | 'running' | 'completed' | 'failed' | 'cancelled'
  run_id: number | null
  error_message: string | null
  added_at: string
  started_at: string | null
  completed_at: string | null
}

export interface HubSettings {
  discord_webhook_url: string
  max_concurrent_runs: number
}

// ---------------------------------------------------------------------------
// Queue API
// ---------------------------------------------------------------------------

export async function listQueue(includeCompleted = false): Promise<QueueEntry[]> {
  const { data } = await API.get('/api/queue', {
    params: { include_completed: includeCompleted },
  })
  return data
}

export async function addToQueue(experimentConfigId: number): Promise<QueueEntry> {
  const { data } = await API.post('/api/queue', {
    experiment_config_id: experimentConfigId,
  })
  return data
}

export async function removeFromQueue(entryId: number): Promise<void> {
  await API.delete(`/api/queue/${entryId}`)
}

export async function reorderQueue(entryIds: number[]): Promise<void> {
  await API.post('/api/queue/reorder', { entry_ids: entryIds })
}

export async function queueHistory(limit = 20): Promise<QueueEntry[]> {
  const { data } = await API.get('/api/queue/history', { params: { limit } })
  return data
}

// ---------------------------------------------------------------------------
// Settings API
// ---------------------------------------------------------------------------

export async function getSettings(): Promise<HubSettings> {
  const { data } = await API.get('/api/settings')
  return data
}

export async function updateSettings(
  updates: Partial<HubSettings>
): Promise<HubSettings> {
  const { data } = await API.put('/api/settings', updates)
  return data
}
