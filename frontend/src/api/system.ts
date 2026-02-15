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

// ---------------------------------------------------------------------------
// System stats (enhanced — used by SystemPage)
// ---------------------------------------------------------------------------

export interface SystemStats {
  cpu: {
    model: string
    physical_cores: number
    logical_cores: number
    percent: number
    per_core_percent: number[]
    frequency_mhz: number | null
    load_avg: { '1min': number; '5min': number; '15min': number }
    top_processes?: Array<{ pid: number; name: string; cpu_percent: number; memory_percent: number }>
  }
  ram: {
    total_gb: number
    used_gb: number
    available_gb: number
    percent: number
    cached_gb: number
    buffers_gb: number
    swap_total_gb: number
    swap_used_gb: number
    swap_percent: number
  }
  disk: {
    partitions: Array<{
      device: string
      mountpoint: string
      fstype: string
      total_gb: number
      used_gb: number
      free_gb: number
      percent: number
    }>
    io_read_mb_s: number
    io_write_mb_s: number
  }
  network: {
    interfaces: Array<{
      name: string
      bytes_sent: number
      bytes_recv: number
      upload_mb_s: number
      download_mb_s: number
    }>
  }
  gpus: Array<{
    index: number
    name: string
    util: number
    memory_used_mb: number
    memory_total_mb: number
    memory_percent: number
    temperature: number | null
    power_draw_w: number | null
    power_limit_w: number | null
    fan_percent: number | null
    clock_graphics_mhz: number | null
    clock_memory_mhz: number | null
    pcie_gen: number | null
    pcie_width: number | null
    driver_version: string | null
    cuda_version: string | null
    processes: Array<{ pid: number; name: string; gpu_memory_mb: number }>
  }>
  platform: {
    hostname: string
    os: string
    arch: string
    python_version: string
    uptime_hours: number
  }
  apple_silicon?: {
    chip: string
    unified_memory_gb: number
    mps_available: boolean
  }
  training_processes?: Array<{
    pid: number
    name: string
    cpu_percent: number
    memory_percent: number
    memory_mb: number
    running_since: string | null
    run_id: number | null
    cmdline: string
  }>
}

export async function getSystemStats(): Promise<SystemStats> {
  const res = await client.get('/system/stats')
  return res.data
}

// ---------------------------------------------------------------------------
// System history (time-series)
// ---------------------------------------------------------------------------

export interface HistoryPoint {
  timestamp: string
  gpu_util: number | null
  gpu_memory_percent: number | null
  gpu_temperature: number | null
  cpu_percent: number | null
  ram_percent: number | null
  disk_percent: number | null
}

export async function getSystemHistory(
  range: '1h' | '6h' | '24h' = '1h',
  serverId?: number,
): Promise<HistoryPoint[]> {
  const params: Record<string, string> = { range }
  if (serverId !== undefined) params.server_id = String(serverId)
  const res = await client.get('/system/history', { params })
  return res.data
}
