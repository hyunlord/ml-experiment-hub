import { useCallback, useEffect, useState } from 'react'
import {
  Cpu,
  HardDrive,
  MemoryStick,
  Thermometer,
  Gauge,
  Zap,
  Monitor,
  Loader2,
} from 'lucide-react'
import axios from 'axios'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GpuInfo {
  index: number
  name: string
  util: number
  memory_used_mb: number
  memory_total_mb: number
  memory_percent: number
  temperature: number | null
  power_draw_w: number | null
  fan_speed: number | null
  driver_version: string | null
}

interface SystemStats {
  gpus: GpuInfo[]
  cpu: { percent: number | null; count: number | null; freq: number | null }
  ram: { percent: number | null; used_gb: number | null; total_gb: number | null }
  disk: {
    used_gb: number | null
    total_gb: number | null
    free_gb: number | null
    percent: number | null
  }
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
  if (temp >= 85) return 'text-red-500'
  if (temp >= 70) return 'text-amber-500'
  return 'text-green-500'
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

// ---------------------------------------------------------------------------
// Ring gauge component
// ---------------------------------------------------------------------------

function RingGauge({
  value,
  label,
  sublabel,
  icon,
  size = 120,
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
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={8}
            className="text-muted/30"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={8}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={`transition-all duration-500 ${ringColor(value)}`}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {icon}
          <span className="mt-1 text-lg font-bold text-card-foreground">
            {Math.round(value)}%
          </span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-card-foreground">{label}</p>
        {sublabel && (
          <p className="text-xs text-muted-foreground">{sublabel}</p>
        )}
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
}: {
  label: string
  value: number
  detail: string
  icon: React.ReactNode
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
      <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all duration-500 ${utilColor(value)}`}
          style={{ width: `${clamp(value)}%` }}
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// GPU Card
// ---------------------------------------------------------------------------

function GpuCard({ gpu }: { gpu: GpuInfo }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-card-foreground">
            GPU {gpu.index}: {gpu.name}
          </h3>
          {gpu.driver_version && (
            <p className="text-xs text-muted-foreground">
              Driver {gpu.driver_version}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1 ${tempColor(gpu.temperature)}`}>
            <Thermometer className="h-4 w-4" />
            <span className="text-sm font-medium">
              {gpu.temperature != null ? `${gpu.temperature}°C` : 'N/A'}
            </span>
          </div>
          {gpu.power_draw_w != null && (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Zap className="h-4 w-4" />
              <span className="text-sm">{gpu.power_draw_w.toFixed(0)}W</span>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <RingGauge
          value={gpu.util}
          label="Utilization"
          icon={<Gauge className="h-5 w-5 text-muted-foreground" />}
          size={110}
        />
        <RingGauge
          value={gpu.memory_percent}
          label="VRAM"
          sublabel={`${(gpu.memory_used_mb / 1024).toFixed(1)} / ${(gpu.memory_total_mb / 1024).toFixed(1)} GB`}
          icon={<MemoryStick className="h-5 w-5 text-muted-foreground" />}
          size={110}
        />
      </div>
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

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchStats])

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
        <p className="mt-1 text-xs text-muted-foreground">
          Backend may not be running
        </p>
      </div>
    )
  }

  if (!stats) return null

  return (
    <div className="space-y-6">
      {/* GPU section */}
      {stats.gpus.length > 0 ? (
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            GPU
          </h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {stats.gpus.map((gpu) => (
              <GpuCard key={gpu.index} gpu={gpu} />
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-border bg-card p-5">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Monitor className="h-5 w-5" />
            <span className="text-sm">No GPU detected (nvidia-smi not available)</span>
          </div>
        </div>
      )}

      {/* CPU / RAM / Disk */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          System
        </h2>
        <div className="rounded-lg border border-border bg-card p-5 space-y-5">
          <ProgressBar
            label="CPU"
            value={clamp(stats.cpu.percent)}
            detail={
              stats.cpu.count
                ? `${stats.cpu.count} cores${stats.cpu.freq ? ` @ ${stats.cpu.freq.toFixed(0)} MHz` : ''}`
                : '-'
            }
            icon={<Cpu className="h-4 w-4 text-blue-500" />}
          />
          <ProgressBar
            label="RAM"
            value={clamp(stats.ram.percent)}
            detail={
              stats.ram.used_gb != null && stats.ram.total_gb != null
                ? `${stats.ram.used_gb} / ${stats.ram.total_gb} GB`
                : '-'
            }
            icon={<MemoryStick className="h-4 w-4 text-purple-500" />}
          />
          <ProgressBar
            label="Disk"
            value={clamp(stats.disk.percent)}
            detail={
              stats.disk.used_gb != null && stats.disk.total_gb != null
                ? `${stats.disk.used_gb} / ${stats.disk.total_gb} GB (${stats.disk.free_gb} GB free)`
                : '-'
            }
            icon={<HardDrive className="h-4 w-4 text-amber-500" />}
          />
        </div>
      </div>

      {/* Refresh indicator */}
      <p className="text-center text-xs text-muted-foreground">
        Auto-refreshing every {POLL_INTERVAL / 1000}s
      </p>
    </div>
  )
}
