import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
  HardDrive,
  MemoryStick,
  Monitor,
  Network,
  Loader2,
  Server,
  Thermometer,
  Gauge,
  Zap,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import axios from 'axios'
import { getSystemHistory, type HistoryPoint } from '@/api/system'
import { loadThresholds } from './SettingsPage'

// ---------------------------------------------------------------------------
// Types (matching enhanced backend API)
// ---------------------------------------------------------------------------

interface GpuProcess {
  pid: number
  name: string
  gpu_memory_mb: number
}

interface GpuInfo {
  index: number
  name: string
  util: number
  memory_used_mb: number
  memory_total_mb: number
  memory_percent: number
  temperature: number | null
  power_draw_w: number | null
  power_limit_w: number | null
  fan_speed: number | null
  clock_graphics_mhz: number | null
  clock_memory_mhz: number | null
  pcie_gen: number | null
  pcie_width: number | null
  driver_version: string | null
  cuda_version: string | null
  processes: GpuProcess[]
}

interface AppleSiliconInfo {
  chip: string
  unified_memory_total_gb: number
  unified_memory_used_gb: number
  unified_memory_percent: number
  metal_supported: boolean
}

interface CpuInfo {
  model: string
  physical_cores: number
  logical_cores: number
  percent: number
  per_core_percent: number[]
  freq_current_mhz: number | null
  freq_max_mhz: number | null
  load_avg_1m: number | null
  load_avg_5m: number | null
  load_avg_15m: number | null
  top_processes: { pid: number; name: string; cpu_percent: number; memory_percent: number }[]
}

interface RamInfo {
  percent: number
  used_gb: number
  total_gb: number
  available_gb: number
  cached_gb: number
  buffers_gb: number
  swap_used_gb: number
  swap_total_gb: number
  swap_percent: number
}

interface DiskPartition {
  mountpoint: string
  device: string
  fstype: string
  used_gb: number
  total_gb: number
  free_gb: number
  percent: number
}

interface DiskInfo {
  partitions: DiskPartition[]
  io: { read_mb_s: number; write_mb_s: number; read_total_gb: number; write_total_gb: number } | null
}

interface NetInterface {
  name: string
  upload_mb_s: number
  download_mb_s: number
  bytes_sent_gb: number
  bytes_recv_gb: number
}

interface ProcessInfo {
  pid: number
  name: string
  cpu_percent: number
  memory_percent: number
  memory_mb: number
  runtime_seconds: number
}

interface PlatformInfo {
  system: string
  hostname: string
  kernel: string
  architecture: string
  uptime_seconds: number | null
}

interface SystemStats {
  gpus: GpuInfo[]
  gpu_type: 'nvidia' | 'apple_silicon' | 'none'
  apple_silicon?: AppleSiliconInfo
  cpu: CpuInfo
  ram: RamInfo
  disk: DiskInfo
  network: { interfaces: NetInterface[] }
  processes: ProcessInfo[]
  platform: PlatformInfo
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clamp(v: number | null | undefined, min = 0, max = 100): number {
  if (v == null) return 0
  return Math.min(max, Math.max(min, v))
}

function tempColor(temp: number | null): string {
  if (temp == null) return 'text-muted-foreground'
  if (temp >= 90) return 'text-red-500'
  if (temp >= 80) return 'text-amber-500'
  if (temp >= 70) return 'text-yellow-500'
  return 'text-green-500'
}

function tempBadge(temp: number | null): string {
  if (temp == null) return ''
  if (temp >= 90) return 'Critical'
  if (temp >= 80) return 'Warning'
  return 'Normal'
}

function utilColor(pct: number): string {
  if (pct >= 90) return 'bg-red-500'
  if (pct >= 70) return 'bg-amber-500'
  if (pct >= 40) return 'bg-blue-500'
  return 'bg-green-500'
}

function ringColor(pct: number): string {
  if (pct >= 90) return 'text-red-500'
  if (pct >= 70) return 'text-amber-500'
  if (pct >= 40) return 'text-blue-500'
  return 'text-green-500'
}

function formatUptime(seconds: number | null): string {
  if (seconds == null) return '-'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function formatRuntime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

// ---------------------------------------------------------------------------
// Ring gauge component
// ---------------------------------------------------------------------------

function RingGauge({
  value,
  label,
  sublabel,
  icon,
  size = 110,
}: {
  value: number
  label: string
  sublabel?: string
  icon: React.ReactNode
  size?: number
}) {
  const radius = (size - 12) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (clamp(value) / 100) * circumference

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={7}
            className="text-muted/30"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={7}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={`transition-all duration-500 ${ringColor(value)}`}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {icon}
          <span className="mt-0.5 text-base font-bold text-card-foreground">
            {Math.round(value)}%
          </span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-xs font-medium text-card-foreground">{label}</p>
        {sublabel && <p className="text-[11px] text-muted-foreground">{sublabel}</p>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Progress bar
// ---------------------------------------------------------------------------

function ProgressBar({
  label,
  value,
  detail,
  icon,
  colorOverride,
}: {
  label: string
  value: number
  detail: string
  icon: React.ReactNode
  colorOverride?: string
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-card-foreground">
          {icon}
          {label}
        </div>
        <span className="text-xs text-muted-foreground">{detail}</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all duration-500 ${colorOverride || utilColor(value)}`}
          style={{ width: `${clamp(value)}%` }}
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Collapsible section
// ---------------------------------------------------------------------------

function CollapsibleSection({
  title,
  icon,
  children,
  defaultOpen = true,
  badge,
}: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
  badge?: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-lg border border-border bg-card">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-5 py-3 text-left"
      >
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        <span className="flex items-center gap-2 text-sm font-semibold text-card-foreground">
          {icon}
          {title}
        </span>
        {badge && <span className="ml-auto">{badge}</span>}
      </button>
      {open && <div className="border-t border-border px-5 py-4">{children}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Detail row
// ---------------------------------------------------------------------------

function DetailRow({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="flex items-center justify-between py-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-medium text-card-foreground">{value ?? 'N/A'}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// GPU Card (enhanced)
// ---------------------------------------------------------------------------

function GpuCard({ gpu }: { gpu: GpuInfo }) {
  const [showDetails, setShowDetails] = useState(false)

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-card-foreground">
            GPU {gpu.index}: {gpu.name}
          </h3>
          <div className="mt-0.5 flex items-center gap-3 text-[11px] text-muted-foreground">
            {gpu.driver_version && <span>Driver {gpu.driver_version}</span>}
            {gpu.cuda_version && <span>CUDA {gpu.cuda_version}</span>}
            {gpu.pcie_gen != null && gpu.pcie_width != null && (
              <span>
                PCIe Gen{gpu.pcie_gen} x{gpu.pcie_width}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Temperature */}
          <div className={`flex items-center gap-1 ${tempColor(gpu.temperature)}`}>
            <Thermometer className="h-4 w-4" />
            <span className="text-sm font-medium">
              {gpu.temperature != null ? `${gpu.temperature}°C` : 'N/A'}
            </span>
            {gpu.temperature != null && (
              <span className="text-[10px]">({tempBadge(gpu.temperature)})</span>
            )}
          </div>
          {/* Power */}
          {gpu.power_draw_w != null && (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Zap className="h-4 w-4" />
              <span className="text-sm">
                {gpu.power_draw_w.toFixed(0)}W
                {gpu.power_limit_w != null && ` / ${gpu.power_limit_w.toFixed(0)}W`}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Gauges */}
      <div className="grid grid-cols-2 gap-6">
        <RingGauge
          value={gpu.util}
          label="Utilization"
          icon={<Gauge className="h-4 w-4 text-muted-foreground" />}
        />
        <RingGauge
          value={gpu.memory_percent}
          label="VRAM"
          sublabel={`${(gpu.memory_used_mb / 1024).toFixed(1)} / ${(gpu.memory_total_mb / 1024).toFixed(1)} GB`}
          icon={<MemoryStick className="h-4 w-4 text-muted-foreground" />}
        />
      </div>

      {/* Expandable details */}
      <button
        onClick={() => setShowDetails(!showDetails)}
        className="mt-3 flex w-full items-center justify-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
      >
        {showDetails ? (
          <>
            <ChevronDown className="h-3 w-3" /> Less details
          </>
        ) : (
          <>
            <ChevronRight className="h-3 w-3" /> More details
          </>
        )}
      </button>

      {showDetails && (
        <div className="mt-3 space-y-1 border-t border-border pt-3">
          {gpu.fan_speed != null && (
            <DetailRow label="Fan Speed" value={`${gpu.fan_speed}%`} />
          )}
          {gpu.clock_graphics_mhz != null && (
            <DetailRow label="GPU Clock" value={`${gpu.clock_graphics_mhz} MHz`} />
          )}
          {gpu.clock_memory_mhz != null && (
            <DetailRow label="Memory Clock" value={`${gpu.clock_memory_mhz} MHz`} />
          )}

          {/* GPU processes */}
          {gpu.processes && gpu.processes.length > 0 && (
            <div className="mt-2">
              <p className="mb-1 text-[11px] font-medium text-muted-foreground">
                Processes ({gpu.processes.length})
              </p>
              {gpu.processes.map((proc) => (
                <div
                  key={proc.pid}
                  className="flex items-center justify-between py-0.5 text-[11px]"
                >
                  <span className="truncate text-card-foreground">
                    {proc.name}{' '}
                    <span className="text-muted-foreground">(PID {proc.pid})</span>
                  </span>
                  <span className="text-muted-foreground">
                    {(proc.gpu_memory_mb / 1024).toFixed(1)} GB
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Apple Silicon Card
// ---------------------------------------------------------------------------

function AppleSiliconCard({ info }: { info: AppleSiliconInfo }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-card-foreground">{info.chip}</h3>
          <p className="text-[11px] text-muted-foreground">
            Metal {info.metal_supported ? 'Supported' : 'Not Available'} &middot; Unified Memory
          </p>
        </div>
      </div>
      <RingGauge
        value={info.unified_memory_percent}
        label="Unified Memory"
        sublabel={`${info.unified_memory_used_gb.toFixed(1)} / ${info.unified_memory_total_gb.toFixed(1)} GB`}
        icon={<MemoryStick className="h-4 w-4 text-muted-foreground" />}
        size={120}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const POLL_INTERVAL = 3000

export default function SystemPage() {
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [historyRange, setHistoryRange] = useState<'1h' | '6h' | '24h'>('1h')
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const thresholds = useMemo(() => loadThresholds(), [])

  const fetchStats = useCallback(async () => {
    try {
      const { data } = await axios.get('/api/system/stats')
      setStats(data)
      setError('')
    } catch {
      setError('Failed to fetch system stats')
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch history data
  const fetchHistory = useCallback(async () => {
    try {
      const data = await getSystemHistory(historyRange)
      setHistory(data)
    } catch {
      // ignore — history is optional
    }
  }, [historyRange])

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchStats])

  useEffect(() => {
    fetchHistory()
    const interval = setInterval(fetchHistory, 30000) // refresh history every 30s
    return () => clearInterval(interval)
  }, [fetchHistory])

  // Compute active alerts from current stats + thresholds
  const alerts = useMemo(() => {
    if (!stats) return []
    const a: { level: 'warn' | 'crit'; message: string }[] = []

    // GPU temperature
    for (const gpu of stats.gpus) {
      if (gpu.temperature != null) {
        if (gpu.temperature >= thresholds.gpu_temp_crit)
          a.push({ level: 'crit', message: `GPU ${gpu.index} temperature ${gpu.temperature}°C exceeds critical threshold (${thresholds.gpu_temp_crit}°C)` })
        else if (gpu.temperature >= thresholds.gpu_temp_warn)
          a.push({ level: 'warn', message: `GPU ${gpu.index} temperature ${gpu.temperature}°C exceeds warning threshold (${thresholds.gpu_temp_warn}°C)` })
      }
      if (gpu.memory_percent >= thresholds.gpu_mem_crit)
        a.push({ level: 'crit', message: `GPU ${gpu.index} memory ${gpu.memory_percent.toFixed(1)}% exceeds critical threshold (${thresholds.gpu_mem_crit}%)` })
      else if (gpu.memory_percent >= thresholds.gpu_mem_warn)
        a.push({ level: 'warn', message: `GPU ${gpu.index} memory ${gpu.memory_percent.toFixed(1)}% exceeds warning threshold (${thresholds.gpu_mem_warn}%)` })
    }

    // RAM
    if (stats.ram.percent >= thresholds.ram_crit)
      a.push({ level: 'crit', message: `RAM usage ${stats.ram.percent}% exceeds critical threshold (${thresholds.ram_crit}%)` })
    else if (stats.ram.percent >= thresholds.ram_warn)
      a.push({ level: 'warn', message: `RAM usage ${stats.ram.percent}% exceeds warning threshold (${thresholds.ram_warn}%)` })

    // Disk
    for (const part of stats.disk.partitions ?? []) {
      if (part.percent >= thresholds.disk_crit)
        a.push({ level: 'crit', message: `Disk ${part.mountpoint} usage ${part.percent}% exceeds critical threshold (${thresholds.disk_crit}%)` })
      else if (part.percent >= thresholds.disk_warn)
        a.push({ level: 'warn', message: `Disk ${part.mountpoint} usage ${part.percent}% exceeds warning threshold (${thresholds.disk_warn}%)` })
    }

    return a
  }, [stats, thresholds])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error && !stats) {
    return (
      <div className="py-20 text-center">
        <Monitor className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
        <p className="text-muted-foreground">{error}</p>
        <p className="mt-1 text-xs text-muted-foreground">Backend may not be running</p>
      </div>
    )
  }

  if (!stats) return null

  return (
    <div className="space-y-4">
      {/* Platform info bar */}
      {stats.platform && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-border bg-card px-4 py-2 text-xs text-muted-foreground">
          <span>
            <Server className="mr-1 inline h-3 w-3" />
            {stats.platform.hostname}
          </span>
          <span>
            {stats.platform.system} {stats.platform.architecture}
          </span>
          <span>{stats.platform.kernel}</span>
          {stats.platform.uptime_seconds != null && (
            <span>Uptime: {formatUptime(stats.platform.uptime_seconds)}</span>
          )}
        </div>
      )}

      {/* Alert banners */}
      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((alert, i) => (
            <div
              key={i}
              className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm ${
                alert.level === 'crit'
                  ? 'border-red-500/30 bg-red-500/10 text-red-500'
                  : 'border-yellow-500/30 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
              }`}
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {alert.message}
            </div>
          ))}
        </div>
      )}

      {/* GPU section */}
      {stats.gpu_type === 'nvidia' && stats.gpus.length > 0 ? (
        <CollapsibleSection
          title="GPU"
          icon={<Monitor className="h-4 w-4 text-green-500" />}
          badge={
            <span className="rounded bg-green-500/10 px-2 py-0.5 text-[11px] font-medium text-green-500">
              {stats.gpus.length} GPU{stats.gpus.length > 1 ? 's' : ''}
            </span>
          }
        >
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {stats.gpus.map((gpu) => (
              <GpuCard key={gpu.index} gpu={gpu} />
            ))}
          </div>
        </CollapsibleSection>
      ) : stats.gpu_type === 'apple_silicon' && stats.apple_silicon ? (
        <CollapsibleSection
          title="GPU (Apple Silicon)"
          icon={<Monitor className="h-4 w-4 text-blue-500" />}
        >
          <AppleSiliconCard info={stats.apple_silicon} />
        </CollapsibleSection>
      ) : (
        <div className="rounded-lg border border-border bg-card p-5">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Monitor className="h-5 w-5" />
            <div>
              <p className="text-sm">CPU-only mode — no GPU detected</p>
              <p className="text-xs">
                Add a GPU server via{' '}
                <a href="/settings" className="text-primary hover:underline">
                  Settings &gt; Servers
                </a>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* CPU section */}
      <CollapsibleSection
        title="CPU"
        icon={<Cpu className="h-4 w-4 text-blue-500" />}
        badge={
          <span className="text-[11px] text-muted-foreground">
            {Math.round(stats.cpu.percent)}%
          </span>
        }
      >
        <div className="space-y-4">
          {/* CPU header info */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span className="font-medium text-card-foreground">{stats.cpu.model}</span>
            <span>
              {stats.cpu.physical_cores}P / {stats.cpu.logical_cores}L cores
            </span>
            {stats.cpu.freq_current_mhz != null && (
              <span>
                {stats.cpu.freq_current_mhz.toFixed(0)} MHz
                {stats.cpu.freq_max_mhz ? ` / ${stats.cpu.freq_max_mhz.toFixed(0)} MHz` : ''}
              </span>
            )}
          </div>

          {/* Overall utilization bar */}
          <ProgressBar
            label="Overall"
            value={clamp(stats.cpu.percent)}
            detail={`${stats.cpu.percent?.toFixed(1)}%`}
            icon={<Cpu className="h-3.5 w-3.5 text-blue-500" />}
          />

          {/* Load average */}
          {stats.cpu.load_avg_1m != null && (
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>
                Load avg: <span className="font-medium text-card-foreground">{stats.cpu.load_avg_1m}</span> (1m)
              </span>
              <span>{stats.cpu.load_avg_5m} (5m)</span>
              <span>{stats.cpu.load_avg_15m} (15m)</span>
            </div>
          )}

          {/* Per-core bars (collapsible) */}
          {stats.cpu.per_core_percent && stats.cpu.per_core_percent.length > 0 && (
            <PerCoreBars cores={stats.cpu.per_core_percent} />
          )}
        </div>
      </CollapsibleSection>

      {/* RAM section */}
      <CollapsibleSection
        title="RAM"
        icon={<MemoryStick className="h-4 w-4 text-purple-500" />}
        badge={
          <span className="text-[11px] text-muted-foreground">
            {stats.ram.used_gb} / {stats.ram.total_gb} GB
          </span>
        }
      >
        <div className="space-y-3">
          <ProgressBar
            label="Used"
            value={clamp(stats.ram.percent)}
            detail={`${stats.ram.used_gb} / ${stats.ram.total_gb} GB (${stats.ram.percent}%)`}
            icon={<MemoryStick className="h-3.5 w-3.5 text-purple-500" />}
          />

          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
            <DetailRow label="Available" value={`${stats.ram.available_gb} GB`} />
            <DetailRow label="Cached" value={`${stats.ram.cached_gb} GB`} />
            <DetailRow label="Buffers" value={`${stats.ram.buffers_gb} GB`} />
            <div />
          </div>

          {/* Swap */}
          {stats.ram.swap_total_gb > 0 && (
            <div>
              <ProgressBar
                label="Swap"
                value={clamp(stats.ram.swap_percent)}
                detail={`${stats.ram.swap_used_gb} / ${stats.ram.swap_total_gb} GB`}
                icon={<HardDrive className="h-3.5 w-3.5 text-orange-500" />}
                colorOverride={stats.ram.swap_percent > 50 ? 'bg-amber-500' : 'bg-green-500'}
              />
              {stats.ram.swap_percent > 50 && (
                <p className="mt-1 text-[11px] text-amber-500">
                  High swap usage — consider adding more RAM
                </p>
              )}
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* Disk section */}
      <CollapsibleSection
        title="Disk"
        icon={<HardDrive className="h-4 w-4 text-amber-500" />}
      >
        <div className="space-y-3">
          {stats.disk.partitions?.map((part) => (
            <ProgressBar
              key={part.mountpoint}
              label={part.mountpoint}
              value={clamp(part.percent)}
              detail={`${part.used_gb} / ${part.total_gb} GB (${part.free_gb} GB free)`}
              icon={<HardDrive className="h-3.5 w-3.5 text-amber-500" />}
            />
          ))}

          {/* IO speeds */}
          {stats.disk.io && (
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>
                Read:{' '}
                <span className="font-medium text-card-foreground">
                  {stats.disk.io.read_mb_s} MB/s
                </span>
              </span>
              <span>
                Write:{' '}
                <span className="font-medium text-card-foreground">
                  {stats.disk.io.write_mb_s} MB/s
                </span>
              </span>
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* Network section */}
      {stats.network?.interfaces && stats.network.interfaces.length > 0 && (
        <CollapsibleSection
          title="Network"
          icon={<Network className="h-4 w-4 text-cyan-500" />}
        >
          <div className="space-y-3">
            {stats.network.interfaces.map((iface) => (
              <div
                key={iface.name}
                className="flex items-center justify-between rounded-md border border-border px-3 py-2"
              >
                <span className="text-sm font-medium text-card-foreground">{iface.name}</span>
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-green-500">
                    &uarr; {iface.upload_mb_s.toFixed(2)} MB/s
                  </span>
                  <span className="text-blue-500">
                    &darr; {iface.download_mb_s.toFixed(2)} MB/s
                  </span>
                  <span className="text-muted-foreground">
                    Sent: {iface.bytes_sent_gb.toFixed(1)} GB
                  </span>
                  <span className="text-muted-foreground">
                    Recv: {iface.bytes_recv_gb.toFixed(1)} GB
                  </span>
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Processes section */}
      {stats.processes && stats.processes.length > 0 && (
        <CollapsibleSection
          title="Training Processes"
          icon={<Activity className="h-4 w-4 text-emerald-500" />}
          badge={
            <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-500">
              {stats.processes.length}
            </span>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-2 pr-3 font-medium">PID</th>
                  <th className="pb-2 pr-3 font-medium">Name</th>
                  <th className="pb-2 pr-3 text-right font-medium">CPU%</th>
                  <th className="pb-2 pr-3 text-right font-medium">MEM%</th>
                  <th className="pb-2 pr-3 text-right font-medium">Memory</th>
                  <th className="pb-2 text-right font-medium">Runtime</th>
                </tr>
              </thead>
              <tbody>
                {stats.processes.map((proc) => (
                  <tr key={proc.pid} className="border-b border-border/50">
                    <td className="py-1.5 pr-3 text-muted-foreground">{proc.pid}</td>
                    <td className="max-w-[200px] truncate py-1.5 pr-3 text-card-foreground">
                      {proc.name}
                    </td>
                    <td className="py-1.5 pr-3 text-right">{proc.cpu_percent}%</td>
                    <td className="py-1.5 pr-3 text-right">{proc.memory_percent}%</td>
                    <td className="py-1.5 pr-3 text-right">
                      {proc.memory_mb > 1024
                        ? `${(proc.memory_mb / 1024).toFixed(1)} GB`
                        : `${proc.memory_mb.toFixed(0)} MB`}
                    </td>
                    <td className="py-1.5 text-right text-muted-foreground">
                      {formatRuntime(proc.runtime_seconds)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}

      {/* History charts */}
      <CollapsibleSection
        title="History"
        icon={<Clock className="h-4 w-4 text-indigo-500" />}
        badge={
          <div className="flex gap-1">
            {(['1h', '6h', '24h'] as const).map((r) => (
              <button
                key={r}
                onClick={(e) => { e.stopPropagation(); setHistoryRange(r) }}
                className={`rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
                  historyRange === r
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:text-foreground'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        }
      >
        {history.length === 0 ? (
          <p className="text-center text-sm text-muted-foreground py-8">
            No history data yet. Data is collected every 10 seconds.
          </p>
        ) : (
          <div className="space-y-6">
            {/* CPU & RAM chart */}
            <div>
              <h4 className="mb-2 text-xs font-medium text-muted-foreground">CPU & RAM Usage (%)</h4>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="timestamp"
                    stroke="hsl(var(--muted-foreground))"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v: string) => {
                      const d = new Date(v)
                      return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
                    }}
                  />
                  <YAxis domain={[0, 100]} stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8, fontSize: 12 }}
                    labelFormatter={(v: string) => new Date(v).toLocaleTimeString()}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="cpu_percent" name="CPU %" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
                  <Line type="monotone" dataKey="ram_percent" name="RAM %" stroke="#a855f7" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* GPU chart (only if data has GPU values) */}
            {history.some((h) => h.gpu_util != null) && (
              <div>
                <h4 className="mb-2 text-xs font-medium text-muted-foreground">GPU Utilization & Memory (%)</h4>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="timestamp"
                      stroke="hsl(var(--muted-foreground))"
                      tick={{ fontSize: 10 }}
                      tickFormatter={(v: string) => {
                        const d = new Date(v)
                        return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
                      }}
                    />
                    <YAxis domain={[0, 100]} stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8, fontSize: 12 }}
                      labelFormatter={(v: string) => new Date(v).toLocaleTimeString()}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="gpu_util" name="GPU Util %" stroke="#10b981" dot={false} strokeWidth={1.5} />
                    <Line type="monotone" dataKey="gpu_memory_percent" name="GPU Mem %" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* GPU Temperature chart */}
            {history.some((h) => h.gpu_temperature != null) && (
              <div>
                <h4 className="mb-2 text-xs font-medium text-muted-foreground">GPU Temperature (°C)</h4>
                <ResponsiveContainer width="100%" height={160}>
                  <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="timestamp"
                      stroke="hsl(var(--muted-foreground))"
                      tick={{ fontSize: 10 }}
                      tickFormatter={(v: string) => {
                        const d = new Date(v)
                        return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
                      }}
                    />
                    <YAxis stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8, fontSize: 12 }}
                      labelFormatter={(v: string) => new Date(v).toLocaleTimeString()}
                    />
                    <Line type="monotone" dataKey="gpu_temperature" name="Temp °C" stroke="#ef4444" dot={false} strokeWidth={1.5} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}
      </CollapsibleSection>

      {/* Refresh indicator */}
      <p className="text-center text-xs text-muted-foreground">
        Auto-refreshing every {POLL_INTERVAL / 1000}s
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Per-core bars (collapsible sub-component)
// ---------------------------------------------------------------------------

function PerCoreBars({ cores }: { cores: number[] }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
      >
        {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Per-core utilization ({cores.length} cores)
      </button>
      {expanded && (
        <div className="mt-2 grid grid-cols-4 gap-x-3 gap-y-1.5 sm:grid-cols-8 lg:grid-cols-12">
          {cores.map((pct, i) => (
            <div key={i} className="text-center">
              <div className="mx-auto h-12 w-3 overflow-hidden rounded-full bg-muted">
                <div
                  className={`w-full rounded-full transition-all duration-300 ${utilColor(pct)}`}
                  style={{ height: `${clamp(pct)}%`, marginTop: `${100 - clamp(pct)}%` }}
                />
              </div>
              <span className="mt-0.5 block text-[9px] text-muted-foreground">{i}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
