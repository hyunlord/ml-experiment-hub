/**
 * Dataset API client.
 *
 * Endpoints for listing datasets, checking status, previewing JSONL,
 * and triggering JSONL prepare jobs.
 */

import client from './client'

export type DatasetStatus = 'ready' | 'raw_only' | 'not_found' | 'preparing'

export interface Dataset {
  id: number
  key: string
  name: string
  description: string
  data_root: string
  jsonl_path: string
  raw_path: string
  raw_format: string
  status: DatasetStatus
  entry_count: number | null
  size_bytes: number | null
  prepare_job_id: number | null
  prepare_progress: number | null
}

export interface PreviewSample {
  image?: string
  caption?: string
  caption_ko?: string
  caption_en?: string
  text?: string
  split?: string
  _caption_lang?: string
  _caption_ko_lang?: string
  _caption_en_lang?: string
  _image_exists?: boolean
  _image_url?: string
  [key: string]: unknown
}

export interface PreviewResponse {
  dataset_id: number
  dataset_name: string
  samples: PreviewSample[]
  language_stats: Record<string, number>
  total_entries: number | null
}

export interface PrepareResponse {
  job_id: number
  dataset_id: number
  message: string
}

export async function listDatasets(): Promise<Dataset[]> {
  const res = await client.get('/datasets')
  return res.data
}

export async function getDataset(id: number): Promise<Dataset> {
  const res = await client.get(`/datasets/${id}`)
  return res.data
}

export async function previewDataset(id: number, n = 5): Promise<PreviewResponse> {
  const res = await client.get(`/datasets/${id}/preview`, { params: { n } })
  return res.data
}

export async function prepareDataset(id: number): Promise<PrepareResponse> {
  const res = await client.post(`/datasets/${id}/prepare`)
  return res.data
}
