import { useMemo, useRef, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Brush,
  ReferenceArea,
} from 'recharts'
import { cn } from '@/lib/utils'
import type { MetricMessage } from './types'

const LOSS_COMPONENTS = [
  'contrastive',
  'eaql',
  'ortho',
  'balance',
  'consistency',
  'lcs',
]

const COLORS: Record<string, string> = {
  contrastive: '#3b82f6',
  eaql: '#ef4444',
  ortho: '#10b981',
  balance: '#f59e0b',
  consistency: '#8b5cf6',
  lcs: '#ec4899',
}

interface LossCurvesTabProps {
  metrics: MetricMessage[]
}

export default function LossCurvesTab({ metrics }: LossCurvesTabProps) {
  const [selected, setSelected] = useState<Set<string>>(
    new Set(['contrastive', 'eaql', 'ortho']),
  )
  const prevDataLen = useRef(0)

  const toggle = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  // Build epoch-based chart data with train/val per loss component
  const chartData = useMemo(() => {
    const byEpoch = new Map<number, Record<string, number>>()

    for (const m of metrics) {
      if (m.epoch == null) continue
      const epoch = Math.floor(m.epoch)
      if (!byEpoch.has(epoch)) byEpoch.set(epoch, { epoch })
      const row = byEpoch.get(epoch)!
      const mets = m.metrics || {}

      for (const comp of LOSS_COMPONENTS) {
        if (mets[`train/${comp}`] != null) row[`train/${comp}`] = mets[`train/${comp}`]
        if (mets[`val/${comp}`] != null) row[`val/${comp}`] = mets[`val/${comp}`]
      }
    }

    return Array.from(byEpoch.values()).sort((a, b) => a.epoch - b.epoch)
  }, [metrics])

  // Animate when new data arrives
  const isNewData = chartData.length > prevDataLen.current
  prevDataLen.current = chartData.length

  const activeComponents = LOSS_COMPONENTS.filter((c) => selected.has(c))

  return (
    <div className="space-y-4">
      {/* Component selector */}
      <div className="flex flex-wrap gap-2">
        {LOSS_COMPONENTS.map((comp) => (
          <button
            key={comp}
            type="button"
            onClick={() => toggle(comp)}
            className={cn(
              'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
              selected.has(comp)
                ? 'border-transparent text-white'
                : 'border-input bg-background text-muted-foreground hover:bg-accent',
            )}
            style={
              selected.has(comp) ? { backgroundColor: COLORS[comp] } : undefined
            }
          >
            {comp}
          </button>
        ))}
      </div>

      {/* Charts per selected component */}
      {activeComponents.length === 0 ? (
        <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-border">
          <p className="text-sm text-muted-foreground">Select loss components above</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {activeComponents.map((comp) => (
            <ZoomableChart
              key={comp}
              comp={comp}
              chartData={chartData}
              animate={isNewData}
            />
          ))}
        </div>
      )}
    </div>
  )
}

/** Individual loss chart with drag-to-zoom support */
function ZoomableChart({
  comp,
  chartData,
  animate,
}: {
  comp: string
  chartData: Record<string, number>[]
  animate: boolean
}) {
  const [zoomLeft, setZoomLeft] = useState<number | null>(null)
  const [zoomRight, setZoomRight] = useState<number | null>(null)
  const [domain, setDomain] = useState<[number, number] | null>(null)

  const handleMouseDown = (e: { activeLabel?: string }) => {
    if (e?.activeLabel != null) setZoomLeft(Number(e.activeLabel))
  }

  const handleMouseMove = (e: { activeLabel?: string }) => {
    if (zoomLeft != null && e?.activeLabel != null) setZoomRight(Number(e.activeLabel))
  }

  const handleMouseUp = () => {
    if (zoomLeft != null && zoomRight != null && zoomLeft !== zoomRight) {
      const left = Math.min(zoomLeft, zoomRight)
      const right = Math.max(zoomLeft, zoomRight)
      setDomain([left, right])
    }
    setZoomLeft(null)
    setZoomRight(null)
  }

  const resetZoom = () => setDomain(null)

  const visibleData = domain
    ? chartData.filter((d) => d.epoch >= domain[0] && d.epoch <= domain[1])
    : chartData

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-card-foreground capitalize">
          {comp}
        </h3>
        {domain && (
          <button
            type="button"
            onClick={resetZoom}
            className="rounded px-2 py-0.5 text-xs text-primary hover:bg-primary/10"
          >
            Reset zoom
          </button>
        )}
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart
          data={visibleData}
          onMouseDown={handleMouseDown as never}
          onMouseMove={handleMouseMove as never}
          onMouseUp={handleMouseUp}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="epoch" stroke="hsl(var(--muted-foreground))" fontSize={11} />
          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
          <Tooltip
            contentStyle={{
              background: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey={`train/${comp}`}
            stroke={COLORS[comp]}
            strokeWidth={2}
            dot={false}
            animationDuration={animate ? 300 : 0}
            name={`train/${comp}`}
          />
          <Line
            type="monotone"
            dataKey={`val/${comp}`}
            stroke={COLORS[comp]}
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            animationDuration={animate ? 300 : 0}
            name={`val/${comp}`}
          />
          {!domain && (
            <Brush
              dataKey="epoch"
              height={20}
              stroke="hsl(var(--border))"
              fill="hsl(var(--muted))"
            />
          )}
          {zoomLeft != null && zoomRight != null && (
            <ReferenceArea
              x1={Math.min(zoomLeft, zoomRight)}
              x2={Math.max(zoomLeft, zoomRight)}
              strokeOpacity={0.3}
              fill="hsl(var(--primary))"
              fillOpacity={0.1}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
