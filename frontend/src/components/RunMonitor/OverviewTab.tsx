import { useMemo, useRef } from 'react'
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
import { cn } from '@/lib/utils'
import type { MetricMessage } from './types'

interface OverviewTabProps {
  metrics: MetricMessage[]
  status: string
}

export default function OverviewTab({ metrics, status }: OverviewTabProps) {
  const prevLossLen = useRef(0)
  const prevMapLen = useRef(0)

  // Compute stats from accumulated metrics
  const stats = useMemo(() => {
    let lastEpoch: number | null = null
    let maxEpochs: number | null = null
    let lastStep = 0
    let bestVal = Infinity
    let bestValEpoch = 0
    let currentLr: number | null = null
    let startTime: number | null = null
    let lastTime: number | null = null

    for (const m of metrics) {
      if (m.epoch != null) lastEpoch = m.epoch
      if (m.step > lastStep) lastStep = m.step
      if (m.timestamp) {
        const t = new Date(m.timestamp).getTime()
        if (!startTime) startTime = t
        lastTime = t
      }

      const mets = m.metrics || {}
      if (mets['val/total'] != null && Number.isFinite(mets['val/total'])) {
        if (mets['val/total'] < bestVal) {
          bestVal = mets['val/total']
          bestValEpoch = m.epoch ?? 0
        }
      }
      if (mets['lr'] != null) currentLr = mets['lr']
      if (mets['max_epochs'] != null) maxEpochs = mets['max_epochs']
    }

    // ETA estimation based on average epoch duration
    let eta = ''
    if (startTime && lastTime && lastEpoch != null && maxEpochs && lastEpoch > 0) {
      const elapsed = lastTime - startTime
      const perEpoch = elapsed / lastEpoch
      const remaining = (maxEpochs - lastEpoch) * perEpoch
      const hours = Math.floor(remaining / 3600000)
      const mins = Math.floor((remaining % 3600000) / 60000)
      eta = hours > 0 ? `~${hours}h ${mins}m` : `~${mins}m`
    }

    return {
      epoch: lastEpoch,
      maxEpochs,
      step: lastStep,
      bestVal: bestVal === Infinity ? null : bestVal,
      bestValEpoch,
      currentLr,
      eta,
    }
  }, [metrics])

  // Chart data: epoch-based train/val total
  const lossChartData = useMemo(() => {
    const byEpoch = new Map<number, Record<string, number>>()
    for (const m of metrics) {
      if (m.epoch == null) continue
      const epoch = Math.floor(m.epoch)
      if (!byEpoch.has(epoch)) byEpoch.set(epoch, { epoch })
      const row = byEpoch.get(epoch)!
      const mets = m.metrics || {}
      if (mets['train/total'] != null) row['train/total'] = mets['train/total']
      if (mets['val/total'] != null) row['val/total'] = mets['val/total']
    }
    return Array.from(byEpoch.values()).sort((a, b) => a.epoch - b.epoch)
  }, [metrics])

  // Chart data: epoch-based mAP
  const mapChartData = useMemo(() => {
    const byEpoch = new Map<number, Record<string, number>>()
    for (const m of metrics) {
      if (m.epoch == null) continue
      const epoch = Math.floor(m.epoch)
      if (!byEpoch.has(epoch)) byEpoch.set(epoch, { epoch })
      const row = byEpoch.get(epoch)!
      const mets = m.metrics || {}
      if (mets['val/map_i2t'] != null) row['val/map_i2t'] = mets['val/map_i2t']
      if (mets['val/map_t2i'] != null) row['val/map_t2i'] = mets['val/map_t2i']
    }
    return Array.from(byEpoch.values()).sort((a, b) => a.epoch - b.epoch)
  }, [metrics])

  // Animate only the newest data point
  const lossAnimating = lossChartData.length > prevLossLen.current
  prevLossLen.current = lossChartData.length
  const mapAnimating = mapChartData.length > prevMapLen.current
  prevMapLen.current = mapChartData.length

  const statusDotColor =
    status === 'running'
      ? 'bg-green-500'
      : status === 'completed'
        ? 'bg-blue-500'
        : status === 'failed'
          ? 'bg-red-500'
          : 'bg-yellow-500'

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {/* Status card with dot indicator */}
        <div className="rounded-lg border border-border bg-card px-4 py-3">
          <p className="text-xs font-medium text-muted-foreground">Status</p>
          <div className="mt-1 flex items-center gap-2">
            <span
              className={cn(
                'inline-block h-2.5 w-2.5 shrink-0 rounded-full',
                statusDotColor,
                status === 'running' && 'animate-pulse',
              )}
            />
            <p className="text-sm font-semibold text-card-foreground">
              {status === 'running'
                ? `Running${stats.epoch != null ? ` (epoch ${stats.epoch}${stats.maxEpochs ? `/${stats.maxEpochs}` : ''}, step ${stats.step})` : ''}`
                : status.charAt(0).toUpperCase() + status.slice(1)}
            </p>
          </div>
        </div>
        <StatCard
          label="Best val/total"
          value={stats.bestVal != null ? `${stats.bestVal.toFixed(4)} (epoch ${stats.bestValEpoch})` : '—'}
        />
        <StatCard
          label="Current LR"
          value={stats.currentLr != null ? stats.currentLr.toExponential(1) : '—'}
        />
        <StatCard
          label="ETA"
          value={stats.eta || '—'}
        />
      </div>

      {/* Loss Chart */}
      {lossChartData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-card-foreground">
            Training / Validation Loss
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={lossChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="epoch" stroke="hsl(var(--muted-foreground))" fontSize={12} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
              <Tooltip
                contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8 }}
                labelStyle={{ color: 'hsl(var(--card-foreground))' }}
              />
              <Legend />
              <Line type="monotone" dataKey="train/total" stroke="#3b82f6" strokeWidth={2} dot={false} animationDuration={lossAnimating ? 300 : 0} />
              <Line type="monotone" dataKey="val/total" stroke="#ef4444" strokeWidth={2} dot={false} animationDuration={lossAnimating ? 300 : 0} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* mAP Chart */}
      {mapChartData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-card-foreground">
            Retrieval mAP
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={mapChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="epoch" stroke="hsl(var(--muted-foreground))" fontSize={12} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} domain={[0, 1]} />
              <Tooltip
                contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8 }}
              />
              <Legend />
              <Line type="monotone" dataKey="val/map_i2t" stroke="#10b981" strokeWidth={2} dot={false} animationDuration={mapAnimating ? 300 : 0} />
              <Line type="monotone" dataKey="val/map_t2i" stroke="#f59e0b" strokeWidth={2} dot={false} animationDuration={mapAnimating ? 300 : 0} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {lossChartData.length === 0 && mapChartData.length === 0 && (
        <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-border">
          <p className="text-sm text-muted-foreground">Waiting for metrics...</p>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold text-card-foreground">{value}</p>
    </div>
  )
}
