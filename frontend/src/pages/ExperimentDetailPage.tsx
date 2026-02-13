import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Play, Square, Trash2 } from 'lucide-react'
import { useExperimentStore } from '@/stores/experimentStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import StatusBadge from '@/components/StatusBadge'
import MetricsChart from '@/components/MetricsChart'
import { ExperimentStatus } from '@/types/experiment'

export default function ExperimentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const {
    selectedExperiment,
    metrics,
    loading,
    fetchExperiment,
    fetchMetrics,
    startExperiment,
    stopExperiment,
    deleteExperiment,
    addMetricPoint,
    clearMetrics,
  } = useExperimentStore()

  const wsUrl = id
    ? `ws://localhost:8000/ws/experiments/${id}/metrics`
    : null

  const { messages, isConnected } = useWebSocket(wsUrl)

  useEffect(() => {
    if (id) {
      fetchExperiment(id)
      fetchMetrics(id)
    }
    return () => {
      clearMetrics()
    }
  }, [id, fetchExperiment, fetchMetrics, clearMetrics])

  useEffect(() => {
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1] as unknown
      addMetricPoint(lastMessage as never)
    }
  }, [messages, addMetricPoint])

  const handleStart = async () => {
    if (id) {
      await startExperiment(id)
    }
  }

  const handleStop = async () => {
    if (id) {
      await stopExperiment(id)
    }
  }

  const handleDelete = async () => {
    if (id && confirm('Are you sure you want to delete this experiment?')) {
      await deleteExperiment(id)
      navigate('/')
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
    selectedExperiment.status === ExperimentStatus.PENDING ||
    selectedExperiment.status === ExperimentStatus.CANCELLED
  const canStop = selectedExperiment.status === ExperimentStatus.RUNNING

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
          <div className="flex items-center gap-2">
            <StatusBadge status={selectedExperiment.status} />
            {isConnected && (
              <span className="flex h-2 w-2 rounded-full bg-green-500" />
            )}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">
              Framework
            </h3>
            <p className="text-card-foreground">{selectedExperiment.framework}</p>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">
              Created
            </h3>
            <p className="text-card-foreground">
              {new Date(selectedExperiment.created_at).toLocaleString()}
            </p>
          </div>
          {selectedExperiment.started_at && (
            <div>
              <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                Started
              </h3>
              <p className="text-card-foreground">
                {new Date(selectedExperiment.started_at).toLocaleString()}
              </p>
            </div>
          )}
          {selectedExperiment.completed_at && (
            <div>
              <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                Completed
              </h3>
              <p className="text-card-foreground">
                {new Date(selectedExperiment.completed_at).toLocaleString()}
              </p>
            </div>
          )}
        </div>

        <div className="mt-4">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">
            Hyperparameters
          </h3>
          <pre className="rounded-md bg-secondary p-3 text-sm">
            {JSON.stringify(selectedExperiment.hyperparameters, null, 2)}
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
              Start
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
            onClick={handleDelete}
            disabled={loading}
            className="flex items-center gap-2 rounded-md border border-destructive bg-background px-4 py-2 text-sm font-medium text-destructive transition-colors hover:bg-destructive hover:text-destructive-foreground disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        </div>
      </div>

      <MetricsChart metrics={metrics} />

      {metrics.length > 0 && (
        <div className="mt-6 rounded-lg border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold text-card-foreground">
            Metrics Data
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-2 text-left font-medium text-muted-foreground">
                    Step
                  </th>
                  <th className="pb-2 text-left font-medium text-muted-foreground">
                    Name
                  </th>
                  <th className="pb-2 text-left font-medium text-muted-foreground">
                    Value
                  </th>
                  <th className="pb-2 text-left font-medium text-muted-foreground">
                    Timestamp
                  </th>
                </tr>
              </thead>
              <tbody>
                {metrics.slice(-20).reverse().map((metric) => (
                  <tr key={metric.id} className="border-b border-border">
                    <td className="py-2 text-card-foreground">{metric.step}</td>
                    <td className="py-2 text-card-foreground">{metric.name}</td>
                    <td className="py-2 text-card-foreground">
                      {metric.value.toFixed(4)}
                    </td>
                    <td className="py-2 text-muted-foreground">
                      {new Date(metric.timestamp).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
