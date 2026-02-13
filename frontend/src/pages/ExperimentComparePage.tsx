import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
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
import { ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'
import client from '@/api/client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ExperimentData {
  id: number
  name: string
  config: Record<string, unknown>
}

interface MetricPoint {
  step: number
  name: string
  value: number
}

// ---------------------------------------------------------------------------
// Color palette for experiments
// ---------------------------------------------------------------------------

const EXP_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b']

// Metrics shown by default in the overlay chart
const DEFAULT_CHART_METRICS = ['val/map_i2t', 'val/total', 'val/map_t2i']

// Metrics shown in the final comparison table
const FINAL_TABLE_METRICS = [
  'val/map_i2t',
  'val/map_t2i',
  'val/p@1',
  'val/p@5',
  'val/total',
  'train/total',
]

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/** Flatten nested object to dot-notation keys for config comparison. */
function flattenObj(
  obj: Record<string, unknown>,
  prefix = '',
): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key
    if (value != null && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(result, flattenObj(value as Record<string, unknown>, fullKey))
    } else {
      result[fullKey] = value
    }
  }
  return result
}

/** Serialize a value for display in config table. */
function displayValue(val: unknown): string {
  if (val === null || val === undefined) return '—'
  if (Array.isArray(val)) return `[${val.join(', ')}]`
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

/** Check if all values in an array are identical (stringified). */
function allSame(values: unknown[]): boolean {
  if (values.length === 0) return true
  const first = JSON.stringify(values[0])
  return values.every((v) => JSON.stringify(v) === first)
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ExperimentComparePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const ids = useMemo(
    () =>
      (searchParams.get('ids') ?? '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    [searchParams],
  )

  const [experiments, setExperiments] = useState<ExperimentData[]>([])
  const [metricsMap, setMetricsMap] = useState<Map<number, MetricPoint[]>>(new Map())
  const [loading, setLoading] = useState(true)
  const [diffOnly, setDiffOnly] = useState(false)
  const [selectedChartMetrics, setSelectedChartMetrics] = useState<Set<string>>(
    new Set(DEFAULT_CHART_METRICS),
  )

  // Fetch experiments + metrics in parallel
  useEffect(() => {
    if (ids.length === 0) return
    setLoading(true)

    const fetchAll = async () => {
      const results = await Promise.allSettled(
        ids.map(async (id) => {
          const [expRes, metricsRes] = await Promise.all([
            client.get(`/experiments/${id}`),
            client.get(`/experiments/${id}/metrics`),
          ])
          return {
            experiment: expRes.data as Record<string, unknown>,
            metrics: (metricsRes.data ?? []) as MetricPoint[],
          }
        }),
      )

      const exps: ExperimentData[] = []
      const mMap = new Map<number, MetricPoint[]>()

      for (const r of results) {
        if (r.status === 'fulfilled') {
          const raw = r.value.experiment
          const exp: ExperimentData = {
            id: raw.id as number,
            name: raw.name as string,
            config: (raw.config ?? raw.hyperparameters ?? {}) as Record<string, unknown>,
          }
          exps.push(exp)
          mMap.set(exp.id, r.value.metrics)
        }
      }

      setExperiments(exps)
      setMetricsMap(mMap)
      setLoading(false)
    }

    fetchAll()
  }, [ids])

  // ---------------------------------------------------------------------------
  // Config comparison data
  // ---------------------------------------------------------------------------

  const configComparison = useMemo(() => {
    if (experiments.length === 0) return { allKeys: [], flatConfigs: [] }

    const flatConfigs = experiments.map((exp) => flattenObj(exp.config || {}))
    const keySet = new Set<string>()
    for (const fc of flatConfigs) {
      for (const k of Object.keys(fc)) keySet.add(k)
    }
    const allKeys = Array.from(keySet).sort()

    return { allKeys, flatConfigs }
  }, [experiments])

  const visibleConfigKeys = useMemo(() => {
    if (!diffOnly) return configComparison.allKeys
    return configComparison.allKeys.filter((key) => {
      const values = configComparison.flatConfigs.map((fc) => fc[key])
      return !allSame(values)
    })
  }, [diffOnly, configComparison])

  // ---------------------------------------------------------------------------
  // Available metric keys across all experiments
  // ---------------------------------------------------------------------------

  const allMetricKeys = useMemo(() => {
    const keySet = new Set<string>()
    for (const [, points] of metricsMap) {
      for (const p of points) keySet.add(p.name)
    }
    return Array.from(keySet).sort()
  }, [metricsMap])

  // ---------------------------------------------------------------------------
  // Chart data: merge experiment metrics by step for selected chart metrics
  // ---------------------------------------------------------------------------

  const chartDataByMetric = useMemo(() => {
    const result = new Map<string, Record<string, number>[]>()

    for (const metricKey of selectedChartMetrics) {
      const byStep = new Map<number, Record<string, number>>()

      for (const exp of experiments) {
        const points = metricsMap.get(exp.id) ?? []
        for (const p of points) {
          if (p.name !== metricKey) continue
          if (!byStep.has(p.step)) byStep.set(p.step, { step: p.step })
          const row = byStep.get(p.step)!
          row[`exp_${exp.id}`] = p.value
        }
      }

      const sorted = Array.from(byStep.values()).sort((a, b) => a.step - b.step)
      if (sorted.length > 0) {
        result.set(metricKey, sorted)
      }
    }

    return result
  }, [selectedChartMetrics, experiments, metricsMap])

  // ---------------------------------------------------------------------------
  // Final metrics comparison: latest value per metric per experiment
  // ---------------------------------------------------------------------------

  const finalMetrics = useMemo(() => {
    // Get all val/ metrics that exist
    const metricKeys = FINAL_TABLE_METRICS.filter((k) => allMetricKeys.includes(k))
    // Also add any val/ keys not in defaults
    for (const k of allMetricKeys) {
      if (k.startsWith('val/') && !metricKeys.includes(k)) {
        metricKeys.push(k)
      }
    }

    const rows: { key: string; values: Map<number, number | null>; bestId: number | null }[] = []

    for (const key of metricKeys) {
      const values = new Map<number, number | null>()
      let bestVal: number | null = null
      let bestId: number | null = null

      // For loss metrics, lower is better; for others, higher is better
      const lowerIsBetter = key.includes('total') || key.includes('loss')

      for (const exp of experiments) {
        const points = metricsMap.get(exp.id) ?? []
        // Get the last value for this metric
        let lastVal: number | null = null
        for (const p of points) {
          if (p.name === key) lastVal = p.value
        }
        values.set(exp.id, lastVal)

        if (lastVal != null) {
          if (bestVal == null) {
            bestVal = lastVal
            bestId = exp.id
          } else if (lowerIsBetter ? lastVal < bestVal : lastVal > bestVal) {
            bestVal = lastVal
            bestId = exp.id
          }
        }
      }

      rows.push({ key, values, bestId })
    }

    return rows
  }, [experiments, metricsMap, allMetricKeys])

  // ---------------------------------------------------------------------------
  // Toggle chart metric
  // ---------------------------------------------------------------------------

  const toggleChartMetric = (key: string) => {
    setSelectedChartMetrics((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (ids.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">No experiments selected for comparison.</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading experiments...</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-lg font-semibold text-foreground">
            Compare Experiments
          </h1>
          <p className="text-xs text-muted-foreground">
            {experiments.map((e) => `#${e.id} ${e.name}`).join(' vs ')}
          </p>
        </div>
      </div>

      {/* ================================================================ */}
      {/* Config Comparison Table                                          */}
      {/* ================================================================ */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">
            Configuration Comparison
          </h2>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={diffOnly}
              onChange={(e) => setDiffOnly(e.target.checked)}
              className="rounded border-input"
            />
            Show differences only
          </label>
        </div>

        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/50">
                <th className="sticky left-0 bg-muted/50 px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">
                  Parameter
                </th>
                {experiments.map((exp, i) => (
                  <th
                    key={exp.id}
                    className="px-4 py-2.5 text-left text-xs font-semibold"
                    style={{ color: EXP_COLORS[i] }}
                  >
                    #{exp.id} {exp.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleConfigKeys.length === 0 ? (
                <tr>
                  <td
                    colSpan={experiments.length + 1}
                    className="px-4 py-8 text-center text-xs text-muted-foreground"
                  >
                    {diffOnly ? 'All parameters are identical' : 'No configuration data'}
                  </td>
                </tr>
              ) : (
                visibleConfigKeys.map((key) => {
                  const values = configComparison.flatConfigs.map((fc) => fc[key])
                  const isDiff = !allSame(values)
                  // Find the most common value to determine which cells differ
                  const counts = new Map<string, number>()
                  for (const v of values) {
                    const s = JSON.stringify(v)
                    counts.set(s, (counts.get(s) ?? 0) + 1)
                  }
                  let modeStr = ''
                  let modeCount = 0
                  for (const [s, c] of counts) {
                    if (c > modeCount) {
                      modeStr = s
                      modeCount = c
                    }
                  }

                  return (
                    <tr
                      key={key}
                      className={cn(
                        'border-t border-border',
                        isDiff ? 'bg-primary/[0.02]' : '',
                      )}
                    >
                      <td className="sticky left-0 bg-card px-4 py-2 font-mono text-xs text-muted-foreground">
                        {key}
                      </td>
                      {values.map((val, i) => {
                        const isOutlier =
                          isDiff && JSON.stringify(val) !== modeStr
                        return (
                          <td
                            key={experiments[i].id}
                            className={cn(
                              'px-4 py-2 font-mono text-xs',
                              isDiff ? 'text-foreground' : 'text-muted-foreground',
                              isOutlier && 'bg-primary/10 font-semibold',
                            )}
                          >
                            {displayValue(val)}
                            {isOutlier && (
                              <span className="ml-1 text-primary">*</span>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ================================================================ */}
      {/* Metric Overlay Charts                                            */}
      {/* ================================================================ */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-foreground">
          Metric Comparison Charts
        </h2>

        {/* Metric selector */}
        <div className="mb-4 flex flex-wrap gap-2">
          {allMetricKeys.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => toggleChartMetric(key)}
              className={cn(
                'rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
                selectedChartMetrics.has(key)
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-input bg-background text-muted-foreground hover:bg-accent',
              )}
            >
              {key}
            </button>
          ))}
        </div>

        {/* Charts */}
        {chartDataByMetric.size === 0 ? (
          <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-border">
            <p className="text-sm text-muted-foreground">
              Select metrics above to compare
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {Array.from(chartDataByMetric.entries()).map(([metricKey, data]) => (
              <div
                key={metricKey}
                className="rounded-lg border border-border bg-card p-4"
              >
                <h3 className="mb-3 text-sm font-semibold text-card-foreground">
                  {metricKey}
                </h3>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={data}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="hsl(var(--border))"
                    />
                    <XAxis
                      dataKey="step"
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={11}
                    />
                    <YAxis
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={11}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                    />
                    <Legend />
                    {experiments.map((exp, i) => (
                      <Line
                        key={exp.id}
                        type="monotone"
                        dataKey={`exp_${exp.id}`}
                        stroke={EXP_COLORS[i]}
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                        name={`#${exp.id} ${exp.name}`}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ================================================================ */}
      {/* Final Metrics Comparison Table                                    */}
      {/* ================================================================ */}
      {finalMetrics.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-foreground">
            Final Metrics
          </h2>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50">
                  <th className="sticky left-0 bg-muted/50 px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">
                    Metric
                  </th>
                  {experiments.map((exp, i) => (
                    <th
                      key={exp.id}
                      className="px-4 py-2.5 text-left text-xs font-semibold"
                      style={{ color: EXP_COLORS[i] }}
                    >
                      #{exp.id} {exp.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {finalMetrics.map((row) => (
                  <tr key={row.key} className="border-t border-border">
                    <td className="sticky left-0 bg-card px-4 py-2 font-mono text-xs text-muted-foreground">
                      {row.key}
                    </td>
                    {experiments.map((exp) => {
                      const val = row.values.get(exp.id)
                      const isBest = row.bestId === exp.id && val != null
                      return (
                        <td
                          key={exp.id}
                          className={cn(
                            'px-4 py-2 font-mono text-xs tabular-nums',
                            isBest
                              ? 'font-bold text-foreground'
                              : 'text-muted-foreground',
                          )}
                        >
                          {val != null ? val.toFixed(4) : '—'}
                          {isBest && (
                            <span className="ml-1.5" title="Best">
                              🏆
                            </span>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
