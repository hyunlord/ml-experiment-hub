import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { MetricPoint } from '@/types/experiment'

interface MetricsChartProps {
  metrics: MetricPoint[]
}

export default function MetricsChart({ metrics }: MetricsChartProps) {
  if (!metrics.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-border bg-card">
        <p className="text-muted-foreground">No metrics data available</p>
      </div>
    )
  }

  // Group flat MetricPoint records into chart-friendly format: { step, loss, accuracy, ... }
  const { chartData, metricNames } = useMemo(() => {
    const stepMap = new Map<number, Record<string, number>>()
    const names = new Set<string>()

    for (const point of metrics) {
      names.add(point.name)
      const existing = stepMap.get(point.step) ?? { step: point.step }
      existing[point.name] = point.value
      stepMap.set(point.step, existing)
    }

    const sorted = Array.from(stepMap.values()).sort((a, b) => a.step - b.step)
    return { chartData: sorted, metricNames: Array.from(names) }
  }, [metrics])

  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="mb-4 text-lg font-semibold text-card-foreground">
        Training Metrics
      </h3>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="step"
            stroke="hsl(var(--muted-foreground))"
            label={{ value: 'Step', position: 'insideBottom', offset: -5 }}
          />
          <YAxis stroke="hsl(var(--muted-foreground))" />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '0.5rem',
            }}
          />
          <Legend />
          {metricNames.map((key, index) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={colors[index % colors.length]}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
