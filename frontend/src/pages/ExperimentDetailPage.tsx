import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Play, Square, Trash2, Copy } from 'lucide-react'
import { useExperimentStore } from '@/stores/experimentStore'
import StatusBadge from '@/components/StatusBadge'
import MetricsChart from '@/components/MetricsChart'
import { ExperimentStatus } from '@/types/experiment'
import { formatAbsoluteTime } from '@/utils/time'

export default function ExperimentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const {
    selectedExperiment,
    runs,
    metrics,
    loading,
    fetchExperiment,
    fetchRuns,
    startRun,
    stopRun,
    deleteExperiment,
    cloneExperiment,
    clearMetrics,
  } = useExperimentStore()

  useEffect(() => {
    if (id) {
      fetchExperiment(id)
      fetchRuns(id)
    }
    return () => {
      clearMetrics()
    }
  }, [id, fetchExperiment, fetchRuns, clearMetrics])

  const latestRun = runs.length > 0 ? runs[runs.length - 1] : null

  const handleStart = async () => {
    if (id) {
      await startRun(id)
    }
  }

  const handleStop = async () => {
    if (latestRun) {
      await stopRun(latestRun.id)
    }
  }

  const handleDelete = async () => {
    if (id && confirm('Are you sure you want to delete this experiment?')) {
      await deleteExperiment(id)
      navigate('/')
    }
  }

  const handleClone = async () => {
    if (id) {
      const clone = await cloneExperiment(id)
      navigate(`/experiments/${clone.id}`)
    }
  }

  if (loading && !selectedExperiment) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading experiment...</p>
      </div>
    )
  }

  if (!selectedExperiment) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Experiment not found</p>
      </div>
    )
  }

  const canStart =
    selectedExperiment.status === ExperimentStatus.DRAFT ||
    selectedExperiment.status === ExperimentStatus.QUEUED ||
    selectedExperiment.status === ExperimentStatus.CANCELLED
  const canStop = latestRun?.status === 'running'

  return (
    <div>
      <button
        onClick={() => navigate('/')}
        className="mb-6 flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to experiments
      </button>

      <div className="mb-6 rounded-lg border border-border bg-card p-6">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-card-foreground">
              {selectedExperiment.name}
            </h1>
            {selectedExperiment.description && (
              <p className="mt-2 text-muted-foreground">
                {selectedExperiment.description}
              </p>
            )}
          </div>
          <StatusBadge status={selectedExperiment.status} />
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">
              Status
            </h3>
            <p className="uppercase text-card-foreground">{selectedExperiment.status}</p>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">
              Created
            </h3>
            <p className="text-card-foreground">
              {formatAbsoluteTime(selectedExperiment.created_at)}
            </p>
          </div>
          {selectedExperiment.tags.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                Tags
              </h3>
              <div className="flex flex-wrap gap-1">
                {selectedExperiment.tags.map((tag) => (
                  <span key={tag} className="rounded bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="mt-4">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">
            Configuration
          </h3>
          <pre className="rounded-md bg-secondary p-3 text-sm overflow-x-auto">
            {JSON.stringify(selectedExperiment.config, null, 2)}
          </pre>
        </div>

        <div className="mt-6 flex gap-3">
          {canStart && (
            <button
              onClick={handleStart}
              disabled={loading}
              className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              Start Training
            </button>
          )}
          {canStop && (
            <button
              onClick={handleStop}
              disabled={loading}
              className="flex items-center gap-2 rounded-md bg-orange-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-orange-700 disabled:opacity-50"
            >
              <Square className="h-4 w-4" />
              Stop
            </button>
          )}
          <button
            onClick={handleClone}
            disabled={loading}
            className="flex items-center gap-2 rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
          >
            <Copy className="h-4 w-4" />
            Clone
          </button>
          <button
            onClick={handleDelete}
            disabled={loading}
            className="flex items-center gap-2 rounded-md border border-destructive bg-background px-4 py-2 text-sm font-medium text-destructive transition-colors hover:bg-destructive hover:text-destructive-foreground disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        </div>
      </div>

      {/* Runs list */}
      {runs.length > 0 && (
        <div className="mb-6 rounded-lg border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold text-card-foreground">
            Runs
          </h3>
          <div className="space-y-2">
            {runs.map((run) => (
              <div key={run.id} className="flex items-center justify-between rounded-md border border-border px-4 py-2 text-sm">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-muted-foreground">#{run.id}</span>
                  <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${
                    run.status === 'running' ? 'bg-blue-500/20 text-blue-300 border-blue-500/30' :
                    run.status === 'completed' ? 'bg-green-500/20 text-green-300 border-green-500/30' :
                    run.status === 'failed' ? 'bg-red-500/20 text-red-300 border-red-500/30' :
                    'bg-orange-500/20 text-orange-300 border-orange-500/30'
                  }`}>
                    {run.status}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {run.started_at ? formatAbsoluteTime(run.started_at) : ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <MetricsChart metrics={metrics} />
    </div>
  )
}
