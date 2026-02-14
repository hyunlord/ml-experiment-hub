import client from './client'

export interface AutoConfig {
  batch_size: number
  accumulate_grad_batches: number
  num_workers: number
}

export interface GpuInfo {
  name: string
  vram_gb: number
  unified: boolean
  available: boolean
  auto_config: {
    frozen: AutoConfig
    unfrozen: AutoConfig
  }
}

export async function getGpuInfo(): Promise<GpuInfo> {
  const res = await client.get('/system/gpu-info')
  return res.data
}
