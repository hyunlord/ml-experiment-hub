import React, { useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import type { MetricMessage, HashAnalysisDetailMessage, HashSample } from './types'

interface HashAnalysisTabProps {
  metrics: MetricMessage[]
  hashDetails?: HashAnalysisDetailMessage[]
}

export default function HashAnalysisTab({ metrics, hashDetails = [] }: HashAnalysisTabProps) {
  // Extract hash-related metrics from latest data
  const hashData = useMemo(() => {
    const bitActivation: Record<string, number> = {}
    const bitEntropy: Record<string, number> = {}
    let similarityMatrix: number[][] | null = null

    for (const m of metrics) {
      const mets = m.metrics || {}
      for (const [key, val] of Object.entries(mets)) {
        if (key.startsWith('hash/bit_activation_')) {
          bitActivation[key.replace('hash/bit_activation_', 'bit_')] = val
        }
        if (key.startsWith('hash/entropy_')) {
          bitEntropy[key.replace('hash/entropy_', 'bit_')] = val
        }
      }
      // Check for similarity matrix data (sent as a flattened array or nested)
      if (mets['hash/similarity_matrix_size'] != null) {
        const size = Math.round(mets['hash/similarity_matrix_size'])
        const flat: number[] = []
        for (let i = 0; i < size * size; i++) {
          const v = mets[`hash/similarity_${i}`]
          if (v != null) flat.push(v)
        }
        if (flat.length === size * size) {
          similarityMatrix = []
          for (let r = 0; r < size; r++) {
            similarityMatrix.push(flat.slice(r * size, (r + 1) * size))
          }
        }
      }
    }

    return { bitActivation, bitEntropy, similarityMatrix }
  }, [metrics])

  const latestSamples: HashSample[] = useMemo(() => {
    if (!hashDetails || hashDetails.length === 0) return []
    const latest = hashDetails[hashDetails.length - 1]
    return latest.samples || []
  }, [hashDetails])

  const activationData = Object.entries(hashData.bitActivation)
    .sort(([a], [b]) => {
      const numA = parseInt(a.replace('bit_', ''), 10)
      const numB = parseInt(b.replace('bit_', ''), 10)
      return numA - numB
    })
    .map(([name, value]) => ({
      name,
      value: Math.round(value * 100) / 100,
    }))

  const entropyData = Object.entries(hashData.bitEntropy)
    .sort(([a], [b]) => {
      const numA = parseInt(a.replace('bit_', ''), 10)
      const numB = parseInt(b.replace('bit_', ''), 10)
      return numA - numB
    })
    .map(([name, value]) => ({
      name,
      value: Math.round(value * 1000) / 1000,
    }))

  const hasData = activationData.length > 0 || entropyData.length > 0 || hashData.similarityMatrix != null || latestSamples.length > 0

  if (!hasData) {
    return (
      <div className="space-y-6">
        <div className="flex h-64 flex-col items-center justify-center rounded-lg border border-dashed border-border">
          <p className="text-sm text-muted-foreground">
            No hash analysis data available yet
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Hash metrics will appear when the model outputs hash/bit_activation_* and hash/entropy_* keys
          </p>
        </div>

        {/* Placeholder cards showing expected metrics */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <PlaceholderCard title="Bit Activation Rates" description="Per-bit activation frequency across the hash code" />
          <PlaceholderCard title="Similarity Matrix" description="Pairwise similarity between sample hash codes" />
          <PlaceholderCard title="Bit Entropy" description="Information entropy per bit position" />
          <PlaceholderCard title="Sample Hash Codes" description="Sample images with their binary hash codes" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Bit Activation Rates */}
      {activationData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-card-foreground">
            Bit Activation Rates
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={activationData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={10} />
              <YAxis domain={[0, 1]} stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <Tooltip
                contentStyle={{
                  background: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="value" radius={[2, 2, 0, 0]}>
                {activationData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.value > 0.45 && entry.value < 0.55 ? '#10b981' : '#f59e0b'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-xs text-muted-foreground">
            Ideal activation rate is ~0.5 (balanced bits). Green = balanced, Yellow = imbalanced.
          </p>
        </div>
      )}

      {/* Similarity Matrix Heatmap */}
      {hashData.similarityMatrix != null && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-card-foreground">
            Sample Pairs Similarity Matrix
          </h3>
          <SimilarityHeatmap matrix={hashData.similarityMatrix} />
          <p className="mt-2 text-xs text-muted-foreground">
            Hamming similarity between sample pairs. Diagonal should be 1.0 (self-similarity).
          </p>
        </div>
      )}

      {hashData.similarityMatrix == null && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-card-foreground">
            Sample Pairs Similarity Matrix
          </h3>
          <div className="flex h-48 items-center justify-center rounded border border-dashed border-border">
            <p className="text-sm text-muted-foreground">
              Similarity matrix will render when hash/similarity_matrix_size and hash/similarity_* data is available
            </p>
          </div>
        </div>
      )}

      {/* Bit Entropy Distribution */}
      {entropyData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-card-foreground">
            Bit Entropy Distribution
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={entropyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={10} />
              <YAxis domain={[0, 1]} stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <Tooltip
                contentStyle={{
                  background: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="value" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-xs text-muted-foreground">
            Higher entropy indicates more informative bits. Max entropy = 1.0 (perfectly balanced).
          </p>
        </div>
      )}

      {/* Sample Hash Codes with Thumbnails */}
      {latestSamples.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-card-foreground">
            Sample Hash Codes
          </h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {latestSamples.map((sample, i) => (
              <SampleCard key={i} sample={sample} index={i} />
            ))}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Sample images with their generated hash codes. Each cell shows the binary hash value.
          </p>
        </div>
      )}
    </div>
  )
}

function SampleCard({ sample, index }: { sample: HashSample; index: number }) {
  const hashStr = sample.code.join('')
  // Truncate display if hash is long
  const displayCode = hashStr.length > 32
    ? `${hashStr.slice(0, 16)}...${hashStr.slice(-16)}`
    : hashStr

  return (
    <div className="rounded-lg border border-border bg-background p-2">
      {sample.thumbnail && (
        <img
          src={sample.thumbnail.startsWith('data:') ? sample.thumbnail : `data:image/jpeg;base64,${sample.thumbnail}`}
          alt={`Sample ${index}`}
          className="mb-2 aspect-square w-full rounded object-cover"
        />
      )}
      <div className="space-y-1">
        <p className="text-[10px] font-medium text-muted-foreground">
          Sample #{index}
        </p>
        <p className="break-all font-mono text-[9px] leading-tight text-card-foreground" title={hashStr}>
          {displayCode}
        </p>
        <p className="text-[10px] text-muted-foreground">
          {sample.code.length}-bit | {sample.code.filter(b => b === 1).length} active
        </p>
      </div>
    </div>
  )
}

/** CSS-grid based heatmap for similarity matrix */
function SimilarityHeatmap({ matrix }: { matrix: number[][] }) {
  const size = matrix.length
  const cellSize = size <= 8 ? 48 : size <= 16 ? 32 : 24

  return (
    <div className="overflow-x-auto">
      <div
        className="inline-grid gap-px"
        style={{
          gridTemplateColumns: `auto repeat(${size}, ${cellSize}px)`,
          gridTemplateRows: `auto repeat(${size}, ${cellSize}px)`,
        }}
      >
        {/* Top-left corner (empty) */}
        <div />
        {/* Column headers */}
        {matrix[0].map((_, c) => (
          <div
            key={`ch-${c}`}
            className="flex items-end justify-center pb-1 text-[10px] text-muted-foreground"
          >
            {c}
          </div>
        ))}
        {/* Rows */}
        {matrix.map((row, r) => (
          <React.Fragment key={`row-${r}`}>
            {/* Row header */}
            <div className="flex items-center justify-end pr-2 text-[10px] text-muted-foreground">
              {r}
            </div>
            {/* Cells */}
            {row.map((val, c) => {
              const clamped = Math.max(0, Math.min(1, val))
              return (
                <div
                  key={`${r}-${c}`}
                  className="flex items-center justify-center rounded-sm text-[9px] font-mono transition-colors"
                  style={{
                    backgroundColor: heatColor(clamped),
                    color: clamped > 0.6 ? '#fff' : 'hsl(var(--card-foreground))',
                    width: cellSize,
                    height: cellSize,
                  }}
                  title={`[${r},${c}] = ${val.toFixed(3)}`}
                >
                  {size <= 12 ? val.toFixed(2) : ''}
                </div>
              )
            })}
          </React.Fragment>
        ))}
      </div>

      {/* Color scale legend */}
      <div className="mt-3 flex items-center gap-2">
        <span className="text-[10px] text-muted-foreground">0</span>
        <div
          className="h-3 flex-1 rounded"
          style={{
            background: 'linear-gradient(to right, #1e293b, #3b82f6, #8b5cf6, #ec4899)',
          }}
        />
        <span className="text-[10px] text-muted-foreground">1</span>
      </div>
    </div>
  )
}

/** Map [0,1] value to a color for the heatmap */
function heatColor(val: number): string {
  // Cold (dark slate) -> Blue -> Purple -> Hot (pink)
  if (val < 0.33) {
    const t = val / 0.33
    const r = Math.round(30 + t * (59 - 30))
    const g = Math.round(41 + t * (130 - 41))
    const b = Math.round(59 + t * (246 - 59))
    return `rgb(${r},${g},${b})`
  }
  if (val < 0.66) {
    const t = (val - 0.33) / 0.33
    const r = Math.round(59 + t * (139 - 59))
    const g = Math.round(130 + t * (92 - 130))
    const b = Math.round(246 + t * (246 - 246))
    return `rgb(${r},${g},${b})`
  }
  const t = (val - 0.66) / 0.34
  const r = Math.round(139 + t * (236 - 139))
  const g = Math.round(92 + t * (72 - 92))
  const b = Math.round(246 + t * (153 - 246))
  return `rgb(${r},${g},${b})`
}

function PlaceholderCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-sm font-medium text-card-foreground">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
    </div>
  )
}
