/**
 * Dataset API client.
 *
 * Endpoints for listing datasets, CRUD, auto-detect, split management,
 * previewing JSONL, and triggering prepare jobs.
 */

import client from './client'

export type DatasetStatus = 'ready' | 'raw_only' | 'not_found' | 'preparing'

export type DatasetType = 'image-text' | 'text-only' | 'image-only' | 'tabular' | 'custom'

export type DatasetFormat = 'jsonl' | 'csv' | 'parquet' | 'huggingface' | 'directory'

export type SplitMethod = 'ratio' | 'file' | 'field' | 'custom' | 'none'

export interface Dataset {
  id: number
  key: string
  name: string
  description: string
  dataset_type: DatasetType
  dataset_format: DatasetFormat
  data_root: string
  jsonl_path: string
  raw_path: string
  raw_format: string
  split_method: SplitMethod
  splits_config: Record<string, unknown>
  status: DatasetStatus
  entry_count: number | null
  size_bytes: number | null
  is_seed: boolean
  prepare_job_id: number | null
  prepare_progress: number | null
}

export interface CreateDatasetPayload {
  name: string
  key?: string
  description?: string
  dataset_type?: string
  dataset_format?: string
  data_root?: string
  raw_path?: string
  jsonl_path?: string
  raw_format?: string
  split_method?: string
  splits_config?: Record<string, unknown>
}

export interface UpdateDatasetPayload {
  name?: string
  description?: string
  dataset_type?: string
  dataset_format?: string
  data_root?: string
  raw_path?: string
  jsonl_path?: string
  raw_format?: string
  split_method?: string
  splits_config?: Record<string, unknown>
}

export interface DetectResult {
  exists: boolean
  format: string | null
  type: string | null
  entry_count: number | null
  raw_format: string | null
  error?: string | null
}

export interface SplitPreview {
  dataset_id: number
  split_method: string
  splits: Record<string, number>
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
  dataset_type: string
  samples: PreviewSample[]
  language_stats: Record<string, number>
  total_entries: number | null
}

export interface PrepareResponse {
  job_id: number
  dataset_id: number
  message: string
}

// CRUD
export async function listDatasets(): Promise<Dataset[]> {
  const res = await client.get('/datasets')
  return res.data
}

export async function getDataset(id: number): Promise<Dataset> {
  const res = await client.get(`/datasets/${id}`)
  return res.data
}

export async function createDataset(payload: CreateDatasetPayload): Promise<Dataset> {
  const res = await client.post('/datasets', payload)
  return res.data
}

export async function updateDataset(id: number, payload: UpdateDatasetPayload): Promise<Dataset> {
  const res = await client.put(`/datasets/${id}`, payload)
  return res.data
}

export async function deleteDataset(id: number): Promise<void> {
  await client.delete(`/datasets/${id}`)
}

// Auto-detect
export async function detectDataset(path: string): Promise<DetectResult> {
  const res = await client.post('/datasets/detect', { path })
  return res.data
}

// Splits
export async function updateSplits(
  id: number,
  splitMethod: string,
  splitsConfig: Record<string, unknown>,
): Promise<Dataset> {
  const res = await client.put(`/datasets/${id}/splits`, {
    split_method: splitMethod,
    splits_config: splitsConfig,
  })
  return res.data
}

export async function previewSplits(id: number, splitMethod?: string): Promise<SplitPreview> {
  const res = await client.get(`/datasets/${id}/splits/preview`, {
    params: splitMethod ? { split_method: splitMethod } : {},
  })
  return res.data
}

// Preview & Prepare
export async function previewDataset(id: number, n = 5): Promise<PreviewResponse> {
  const res = await client.get(`/datasets/${id}/preview`, { params: { n } })
  return res.data
}

export async function prepareDataset(id: number): Promise<PrepareResponse> {
  const res = await client.post(`/datasets/${id}/prepare`)
  return res.data
}
