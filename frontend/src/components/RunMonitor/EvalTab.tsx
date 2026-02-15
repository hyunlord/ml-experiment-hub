import { useState, useEffect, useCallback } from 'react'
import { Play, Loader2, X, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  createEvalJob,
  getJob,
  listJobs,
  cancelJob,
  type JobResponse,
} from '@/api/jobs'
import { formatAbsoluteTime } from '@/utils/time'

interface EvalTabProps {
  runId: number
}

const CHECKPOINT_OPTIONS = ['best', 'latest'] as const
const BIT_LENGTHS = [8, 16, 32, 64, 128]

export default function EvalTab({ runId }: EvalTabProps) {
  const [checkpoint, setCheckpoint] = useState<string>('best')
  const [customEpoch, setCustomEpoch] = useState('')
  const [bitLengths, setBitLengths] = useState<number[]>([8, 16, 32, 64, 128])
  const [kValues] = useState<number[]>([1, 5, 10])
  const [launching, setLaunching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Jobs tracking
  const [jobs, setJobs] = useState<JobResponse[]>([])
  const [activeJobId, setActiveJobId] = useState<number | null>(null)
  const [activeJob, setActiveJob] = useState<JobResponse | null>(null)

  // Load existing eval jobs for this run
  const loadJobs = useCallback(async () => {
    try {
      const allJobs = await listJobs({ job_type: 'eval', run_id: runId })
      setJobs(allJobs)
    } catch {
      // silently ignore
    }
  }, [runId])

  useEffect(() => {
    loadJobs()
  }, [loadJobs])

  // Poll active job progress
  useEffect(() => {
    if (!activeJobId) return
    const interval = setInterval(async () => {
      try {
        const job = await getJob(activeJobId)
        setActiveJob(job)
        if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
          setActiveJobId(null)
          loadJobs()
        }
      } catch {
        setActiveJobId(null)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [activeJobId, loadJobs])

  const handleLaunch = async () => {
    setLaunching(true)
    setError(null)
    try {
      const ckpt = checkpoint === 'custom' ? customEpoch : checkpoint
      const job = await createEvalJob({
        run_id: runId,
        checkpoint: ckpt,
        bit_lengths: bitLengths,
        k_values: kValues,
      })
      setActiveJobId(job.id)
      setActiveJob(job)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to launch eval job'
      setError(msg)
    } finally {
      setLaunching(false)
    }
  }

  const handleCancel = async () => {
    if (!activeJobId) return
    try {
      await cancelJob(activeJobId)
      setActiveJobId(null)
      setActiveJob(null)
      loadJobs()
    } catch {
      // ignore
    }
  }

  const toggleBit = (bit: number) => {
    setBitLengths((prev) =>
      prev.includes(bit) ? prev.filter((b) => b !== bit) : [...prev, bit].sort((a, b) => a - b),
    )
  }

  // Completed eval jobs with results
  const completedJobs = jobs.filter(
    (j) => j.status === 'completed' && j.result_json && Object.keys(j.result_json).length > 0,
  )

  return (
    <div className="space-y-6">
      {/* Launch Panel */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="mb-4 text-sm font-semibold text-card-foreground">Run Evaluation</h3>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Checkpoint Selector */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              Checkpoint
            </label>
            <div className="flex flex-wrap gap-1.5">
              {CHECKPOINT_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setCheckpoint(opt)}
                  className={cn(
                    'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
                    checkpoint === opt
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:bg-accent',
                  )}
                >
                  {opt}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setCheckpoint('custom')}
                className={cn(
                  'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
                  checkpoint === 'custom'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:bg-accent',
                )}
              >
                epoch
              </button>
            </div>
            {checkpoint === 'custom' && (
              <input
                type="number"
                placeholder="Epoch number"
                value={customEpoch}
                onChange={(e) => setCustomEpoch(e.target.value)}
                className="mt-2 w-full rounded-md border border-border bg-background px-3 py-1.5 text-xs"
              />
            )}
          </div>

          {/* Bit Length Selector */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              Bit Lengths
            </label>
            <div className="flex flex-wrap gap-1.5">
              {BIT_LENGTHS.map((bit) => (
                <button
                  key={bit}
                  type="button"
                  onClick={() => toggleBit(bit)}
                  className={cn(
                    'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
                    bitLengths.includes(bit)
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:bg-accent',
                  )}
                >
                  {bit}
                </button>
              ))}
            </div>
          </div>

          {/* Launch Button */}
          <div className="flex items-end">
            {activeJobId ? (
              <button
                type="button"
                onClick={handleCancel}
                className="flex items-center gap-2 rounded-md border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-500/20"
              >
                <X className="h-4 w-4" />
                Cancel
              </button>
            ) : (
              <button
                type="button"
                onClick={handleLaunch}
                disabled={launching || bitLengths.length === 0}
                className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
              >
                {launching ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Run Evaluation
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-3 flex items-center gap-2 text-xs text-red-500">
            <AlertCircle className="h-3.5 w-3.5" />
            {error}
          </div>
        )}
      </div>

      {/* Active Job Progress */}
      {activeJob && (activeJob.status === 'running' || activeJob.status === 'pending') && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-medium text-card-foreground">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              Evaluation {activeJob.status === 'pending' ? 'starting...' : 'in progress'}
            </div>
            <span className="text-xs tabular-nums text-muted-foreground">
              {activeJob.progress}%
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${activeJob.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Results Table */}
      {completedJobs.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">Evaluation Results</h3>
            <button
              type="button"
              onClick={loadJobs}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
            >
              <RefreshCw className="h-3 w-3" />
              Refresh
            </button>
          </div>

          {completedJobs.map((job) => (
            <EvalResultCard key={job.id} job={job} />
          ))}
        </div>
      )}

      {/* Comparison Table */}
      {completedJobs.length >= 2 && (
        <ComparisonTable jobs={completedJobs} />
      )}
    </div>
  )
}

function EvalResultCard({ job }: { job: JobResponse }) {
  const results = job.result_json as Record<string, Record<string, number>>
  const bitKeys = Object.keys(results).sort((a, b) => Number(a) - Number(b))
  const checkpoint = (job.config_json as Record<string, unknown>).checkpoint ?? 'unknown'

  if (bitKeys.length === 0) return null

  // Get all metric names from first bit length
  const metricNames = Object.keys(results[bitKeys[0]] || {}).sort()

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border bg-muted/50 px-4 py-2">
        <CheckCircle className="h-4 w-4 text-green-500" />
        <span className="text-xs font-medium text-card-foreground">
          Checkpoint: {String(checkpoint)}
        </span>
        <span className="text-xs text-muted-foreground">
          Job #{job.id} &middot; {formatAbsoluteTime(job.created_at)}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Metric</th>
              {bitKeys.map((bit) => (
                <th key={bit} className="px-3 py-2 text-right font-medium text-muted-foreground">
                  {bit}-bit
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metricNames.map((metric) => (
              <tr key={metric} className="border-b border-border last:border-0">
                <td className="px-3 py-2 font-medium text-card-foreground">{metric}</td>
                {bitKeys.map((bit) => (
                  <td key={bit} className="px-3 py-2 text-right tabular-nums text-card-foreground">
                    {results[bit]?.[metric] != null
                      ? results[bit][metric].toFixed(4)
                      : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ComparisonTable({ jobs }: { jobs: JobResponse[] }) {
  // Collect all bit lengths and metrics
  const allBits = new Set<string>()
  const allMetrics = new Set<string>()

  for (const job of jobs) {
    const results = job.result_json as Record<string, Record<string, number>>
    for (const bit of Object.keys(results)) {
      allBits.add(bit)
      for (const metric of Object.keys(results[bit] || {})) {
        allMetrics.add(metric)
      }
    }
  }

  const sortedBits = Array.from(allBits).sort((a, b) => Number(a) - Number(b))
  const sortedMetrics = Array.from(allMetrics).sort()

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="border-b border-border bg-muted/50 px-4 py-2">
        <h3 className="text-xs font-semibold text-card-foreground">
          Checkpoint Comparison ({jobs.length} evaluations)
        </h3>
      </div>

      {sortedBits.map((bit) => (
        <div key={bit} className="border-b border-border last:border-0">
          <div className="bg-muted/20 px-4 py-1.5">
            <span className="text-xs font-semibold text-primary">{bit}-bit</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">
                    Metric
                  </th>
                  {jobs.map((job) => {
                    const ckpt = (job.config_json as Record<string, unknown>).checkpoint
                    return (
                      <th
                        key={job.id}
                        className="px-3 py-1.5 text-right font-medium text-muted-foreground"
                      >
                        {String(ckpt ?? `Job#${job.id}`)}
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {sortedMetrics.map((metric) => {
                  const values = jobs.map((job) => {
                    const results = job.result_json as Record<string, Record<string, number>>
                    return results[bit]?.[metric] ?? null
                  })
                  const validValues = values.filter((v): v is number => v !== null)
                  const bestValue = metric.includes('mAP') || metric.includes('P@')
                    ? Math.max(...validValues)
                    : Math.min(...validValues)

                  return (
                    <tr key={metric} className="border-b border-border last:border-0">
                      <td className="px-3 py-1.5 font-medium text-card-foreground">{metric}</td>
                      {values.map((val, idx) => (
                        <td
                          key={jobs[idx].id}
                          className={cn(
                            'px-3 py-1.5 text-right tabular-nums',
                            val === bestValue && validValues.length > 1
                              ? 'font-bold text-green-600'
                              : 'text-card-foreground',
                          )}
                        >
                          {val != null ? val.toFixed(4) : '—'}
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}
