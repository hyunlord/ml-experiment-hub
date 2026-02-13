import { useMemo } from 'react'
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { cn } from '@/lib/utils'
import type { GpuInfo, SystemMessage } from './types'

interface SystemTabProps {
  systemData: SystemMessage[]
}

export default function SystemTab({ systemData }: SystemTabProps) {
  const last = systemData.length > 0 ? systemData[systemData.length - 1] : null

  // Multi-GPU: prefer gpus array, fall back to flat fields
  const gpus: GpuInfo[] = useMemo(() => {
    if (last?.gpus && last.gpus.length > 0) return last.gpus
    // Synthesize single GPU from flat fields
    if (last?.gpu_util != null || last?.gpu_memory_used != null) {
      return [{
        index: 0,
        name: 'GPU 0',
        util: last.gpu_util ?? 0,
        memory_used_mb: last.gpu_memory_used ?? 0,
        memory_total_mb: last.gpu_memory_total ?? 0,
        memory_percent: last.gpu_memory_used != null && last.gpu_memory_total != null
          ? Math.round((last.gpu_memory_used / last.gpu_memory_total) * 100)
          : 0,
        temperature: null,
      }]
    }
    return []
  }, [last])

  const cpuPercent = last?.cpu_percent ?? last?.cpu?.percent ?? null
  const ramPercent = last?.ram_percent ?? last?.ram?.percent ?? null
  const ramDetail = last?.ram
    ? `${last.ram.used_gb.toFixed(1)} / ${last.ram.total_gb.toFixed(1)} GB`
    : undefined

  // GPU memory bar chart data (used vs free per GPU)
  const gpuMemData = useMemo(() => {
    return gpus.map((g) => ({
      name: gpus.length > 1 ? `GPU ${g.index}` : 'GPU',
      used: Math.round(g.memory_used_mb / 1024 * 10) / 10,
      free: Math.round((g.memory_total_mb - g.memory_used_mb) / 1024 * 10) / 10,
      total: Math.round(g.memory_total_mb / 1024 * 10) / 10,
    }))
  }, [gpus])

  // Last 5 minutes of data for trend chart
  const trendData = useMemo(() => {
    const fiveMinAgo = Date.now() - 5 * 60 * 1000
    return systemData
      .filter((s) => new Date(s.timestamp).getTime() > fiveMinAgo)
      .map((s, i) => ({
        t: i,
        gpu: s.gpu_util ?? s.gpus?.[0]?.util ?? 0,
        cpu: s.cpu_percent ?? s.cpu?.percent ?? 0,
        ram: s.ram_percent ?? s.ram?.percent ?? 0,
      }))
  }, [systemData])

  return (
    <div className="space-y-6">
      {/* GPU Section */}
      {gpus.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-foreground">
            GPU{gpus.length > 1 ? 's' : ''}
          </h3>
          <div className={cn(
            'grid gap-4',
            gpus.length === 1 ? 'grid-cols-2 lg:grid-cols-4' : 'grid-cols-1',
          )}>
            {gpus.map((gpu) => (
              <div key={gpu.index} className="space-y-3">
                {gpus.length > 1 && (
                  <p className="text-xs font-medium text-muted-foreground">
                    GPU {gpu.index}: {gpu.name}
                  </p>
                )}
                <div className={cn(
                  'grid gap-3',
                  gpus.length === 1 ? 'grid-cols-2 lg:grid-cols-4' : 'grid-cols-2 lg:grid-cols-4',
                )}>
                  <GaugeCard
                    label="Utilization"
                    value={Math.round(gpu.util)}
                    unit="%"
                    max={100}
                    color="#3b82f6"
                  />
                  <GaugeCard
                    label="Memory"
                    value={gpu.memory_percent}
                    unit="%"
                    max={100}
                    color="#8b5cf6"
                    detail={`${(gpu.memory_used_mb / 1024).toFixed(1)} / ${(gpu.memory_total_mb / 1024).toFixed(1)} GB`}
                  />
                  <GaugeCard
                    label="Temperature"
                    value={gpu.temperature}
                    unit="\u00B0C"
                    max={100}
                    color={gpu.temperature != null && gpu.temperature > 80 ? '#ef4444' : '#f59e0b'}
                  />
                  {gpus.length === 1 && (
                    <GaugeCard
                      label="Power"
                      value={null}
                      unit="W"
                      max={300}
                      color="#06b6d4"
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* GPU Memory Bar Chart (used vs total per GPU) */}
      {gpuMemData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-card-foreground">
            GPU Memory (Used / Total)
          </h3>
          <ResponsiveContainer width="100%" height={gpuMemData.length > 1 ? 200 : 120}>
            <BarChart data={gpuMemData} layout="vertical" barGap={0}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
              <XAxis type="number" stroke="hsl(var(--muted-foreground))" fontSize={11} unit=" GB" />
              <YAxis type="category" dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={11} width={50} />
              <Tooltip
                contentStyle={{
                  background: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(val: number, name: string) => [`${val} GB`, name === 'used' ? 'Used' : 'Free']}
              />
              <Bar dataKey="used" stackId="mem" fill="#8b5cf6" name="Used" radius={[0, 0, 0, 0]} />
              <Bar dataKey="free" stackId="mem" fill="hsl(var(--muted))" name="Free" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* CPU & RAM */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-foreground">
          CPU & Memory
        </h3>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <GaugeCard
            label="CPU"
            value={cpuPercent != null ? Math.round(cpuPercent) : null}
            unit="%"
            max={100}
            color="#10b981"
            detail={last?.cpu ? `${last.cpu.count} cores` : undefined}
          />
          <GaugeCard
            label="RAM"
            value={ramPercent != null ? Math.round(ramPercent) : null}
            unit="%"
            max={100}
            color="#ec4899"
            detail={ramDetail}
          />
        </div>
      </div>

      {/* Trend Chart (last 5 min) */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="mb-3 text-sm font-semibold text-card-foreground">
          Last 5 Minutes
        </h3>
        {trendData.length > 1 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="t" tick={false} stroke="hsl(var(--muted-foreground))" />
              <YAxis domain={[0, 100]} stroke="hsl(var(--muted-foreground))" fontSize={11} unit="%" />
              <Tooltip
                contentStyle={{
                  background: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelFormatter={() => ''}
                formatter={(val: number, name: string) => [`${Math.round(val)}%`, name]}
              />
              <Area type="monotone" dataKey="gpu" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} strokeWidth={2} name="GPU %" isAnimationActive={false} />
              <Area type="monotone" dataKey="cpu" stroke="#10b981" fill="#10b981" fillOpacity={0.1} strokeWidth={2} name="CPU %" isAnimationActive={false} />
              <Area type="monotone" dataKey="ram" stroke="#ec4899" fill="#ec4899" fillOpacity={0.1} strokeWidth={2} name="RAM %" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-48 items-center justify-center">
            <p className="text-sm text-muted-foreground">Collecting system data...</p>
          </div>
        )}
      </div>
    </div>
  )
}

function GaugeCard({
  label,
  value,
  unit,
  max,
  color,
  detail,
}: {
  label: string
  value: number | null
  unit: string
  max: number
  color: string
  detail?: string
}) {
  const pct = value != null ? Math.min(100, (value / max) * 100) : 0

  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-bold" style={{ color }}>
        {value != null ? `${value}${unit}` : '\u2014'}
      </p>
      {/* Progress bar */}
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
    </div>
  )
}
