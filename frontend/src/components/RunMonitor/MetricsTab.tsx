import { useMemo, useState } from 'react'
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
} from 'recharts'
import { cn } from '@/lib/utils'
import type { MetricMessage } from './types'

const PALETTE = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#a855f7',
]

interface MetricsTabProps {
  metrics: MetricMessage[]
}

/**
 * Assign each selected metric to a y-axis based on value range similarity.
 * Metrics with similar order-of-magnitude share an axis.
 */
function assignAxes(
  selectedArr: string[],
  chartData: Record<string, number>[],
): Map<string, string> {
  if (selectedArr.length <= 1) {
    return new Map(selectedArr.map((k) => [k, 'left']))
  }

  // Compute min/max for each metric
  const ranges = new Map<string, { min: number; max: number }>()
  for (const key of selectedArr) {
    let min = Infinity
    let max = -Infinity
    for (const row of chartData) {
      if (row[key] != null) {
        if (row[key] < min) min = row[key]
        if (row[key] > max) max = row[key]
      }
    }
    if (min !== Infinity) ranges.set(key, { min, max })
  }

  // Simple heuristic: if max of one metric is > 10x max of another, put on separate axis
  const axes = new Map<string, string>()
  const firstKey = selectedArr[0]
  axes.set(firstKey, 'left')
  const firstRange = ranges.get(firstKey)

  for (let i = 1; i < selectedArr.length; i++) {
    const key = selectedArr[i]
    const range = ranges.get(key)
    if (firstRange && range) {
      const firstMag = Math.abs(firstRange.max) || 1
      const curMag = Math.abs(range.max) || 1
      const ratio = Math.max(firstMag / curMag, curMag / firstMag)
      axes.set(key, ratio > 10 ? 'right' : 'left')
    } else {
      axes.set(key, 'left')
    }
  }

  return axes
}

export default function MetricsTab({ metrics }: MetricsTabProps) {
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  // Build metric tree: collect all unique metric keys grouped by prefix
  const metricTree = useMemo(() => {
    const allKeys = new Set<string>()
    for (const m of metrics) {
      for (const key of Object.keys(m.metrics || {})) {
        allKeys.add(key)
      }
    }
    const groups = new Map<string, string[]>()
    for (const key of Array.from(allKeys).sort()) {
      const slashIdx = key.indexOf('/')
      const group = slashIdx > 0 ? key.slice(0, slashIdx) : 'other'
      if (!groups.has(group)) groups.set(group, [])
      groups.get(group)!.push(key)
    }
    return groups
  }, [metrics])

  // Build step-based chart data for selected keys
  const chartData = useMemo(() => {
    if (selectedKeys.size === 0) return []
    const byStep = new Map<number, Record<string, number>>()
    for (const m of metrics) {
      if (!byStep.has(m.step)) byStep.set(m.step, { step: m.step })
      const row = byStep.get(m.step)!
      for (const key of selectedKeys) {
        if (m.metrics?.[key] != null) row[key] = m.metrics[key]
      }
    }
    return Array.from(byStep.values()).sort((a, b) => a.step - b.step)
  }, [metrics, selectedKeys])

  const toggleKey = (key: string) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const toggleGroup = (group: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(group)) next.delete(group)
      else next.add(group)
      return next
    })
  }

  const selectAllInGroup = (keys: string[]) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev)
      const allSelected = keys.every((k) => next.has(k))
      if (allSelected) {
        keys.forEach((k) => next.delete(k))
      } else {
        keys.forEach((k) => next.add(k))
      }
      return next
    })
  }

  const selectedArr = Array.from(selectedKeys)
  const axisMap = useMemo(
    () => assignAxes(selectedArr, chartData),
    [selectedArr, chartData],
  )
  const hasRightAxis = Array.from(axisMap.values()).includes('right')

  return (
    <div className="flex gap-4">
      {/* Left: Metric tree */}
      <div className="w-56 shrink-0 overflow-y-auto rounded-lg border border-border bg-card p-3" style={{ maxHeight: 600 }}>
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase text-muted-foreground">
            Metrics
          </p>
          {selectedKeys.size > 0 && (
            <button
              type="button"
              onClick={() => setSelectedKeys(new Set())}
              className="text-[10px] text-muted-foreground hover:text-foreground"
            >
              Clear all
            </button>
          )}
        </div>
        {metricTree.size === 0 ? (
          <p className="text-xs text-muted-foreground">No metrics yet</p>
        ) : (
          Array.from(metricTree.entries()).map(([group, keys]) => (
            <div key={group} className="mb-3">
              <button
                type="button"
                onClick={() => toggleGroup(group)}
                className="mb-1 flex w-full items-center gap-1 text-xs font-semibold text-card-foreground hover:text-primary"
              >
                <span className="text-[10px]">{collapsedGroups.has(group) ? '▶' : '▼'}</span>
                <span>{group}/</span>
                <span className="ml-auto text-[10px] font-normal text-muted-foreground">
                  {keys.filter((k) => selectedKeys.has(k)).length}/{keys.length}
                </span>
              </button>
              {!collapsedGroups.has(group) && (
                <>
                  <button
                    type="button"
                    onClick={() => selectAllInGroup(keys)}
                    className="mb-0.5 block w-full rounded px-2 py-0.5 text-left text-[10px] text-muted-foreground hover:bg-accent"
                  >
                    {keys.every((k) => selectedKeys.has(k)) ? 'Deselect all' : 'Select all'}
                  </button>
                  {keys.map((key) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => toggleKey(key)}
                      className={cn(
                        'block w-full rounded px-2 py-1 text-left text-xs transition-colors',
                        selectedKeys.has(key)
                          ? 'bg-primary/10 font-medium text-primary'
                          : 'text-muted-foreground hover:bg-accent',
                      )}
                    >
                      {key}
                    </button>
                  ))}
                </>
              )}
            </div>
          ))
        )}
      </div>

      {/* Right: Chart */}
      <div className="flex-1 rounded-lg border border-border bg-card p-4">
        {selectedArr.length === 0 ? (
          <div className="flex h-96 items-center justify-center">
            <p className="text-sm text-muted-foreground">
              Select metrics from the left panel to visualize
            </p>
          </div>
        ) : (
          <>
            {hasRightAxis && (
              <p className="mb-2 text-[10px] text-muted-foreground">
                Dual Y-axis enabled (auto-detected different scales)
              </p>
            )}
            <ResponsiveContainer width="100%" height={500}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="step" stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <YAxis yAxisId="left" stroke="hsl(var(--muted-foreground))" fontSize={11} />
                {hasRightAxis && (
                  <YAxis yAxisId="right" orientation="right" stroke="hsl(var(--muted-foreground))" fontSize={11} />
                )}
                <Tooltip
                  contentStyle={{
                    background: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Legend />
                {selectedArr.map((key, i) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={PALETTE[i % PALETTE.length]}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                    yAxisId={axisMap.get(key) ?? 'left'}
                  />
                ))}
                <Brush
                  dataKey="step"
                  height={20}
                  stroke="hsl(var(--border))"
                  fill="hsl(var(--muted))"
                />
              </LineChart>
            </ResponsiveContainer>
          </>
        )}
      </div>
    </div>
  )
}
