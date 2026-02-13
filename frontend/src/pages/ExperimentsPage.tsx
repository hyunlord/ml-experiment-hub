import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Filter } from 'lucide-react'
import { useExperimentStore } from '@/stores/experimentStore'
import ExperimentCard from '@/components/ExperimentCard'
import { ExperimentStatus } from '@/types/experiment'

export default function ExperimentsPage() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<string>('all')

  const { experiments, loading, fetchExperiments } = useExperimentStore()

  useEffect(() => {
    fetchExperiments(statusFilter !== 'all' ? { status: statusFilter } : undefined)
  }, [fetchExperiments, statusFilter])

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Experiments</h1>
          <p className="mt-2 text-muted-foreground">
            Manage and monitor your ML experiments
          </p>
        </div>
        <button
          onClick={() => navigate('/experiments/new')}
          className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Experiment
        </button>
      </div>

      <div className="mb-6 flex items-center gap-3">
        <Filter className="h-5 w-5 text-muted-foreground" />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All Status</option>
          <option value={ExperimentStatus.DRAFT}>Draft</option>
          <option value={ExperimentStatus.QUEUED}>Queued</option>
          <option value={ExperimentStatus.RUNNING}>Running</option>
          <option value={ExperimentStatus.COMPLETED}>Completed</option>
          <option value={ExperimentStatus.FAILED}>Failed</option>
          <option value={ExperimentStatus.CANCELLED}>Cancelled</option>
        </select>
      </div>

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <p className="text-muted-foreground">Loading experiments...</p>
        </div>
      ) : experiments.length === 0 ? (
        <div className="flex h-64 flex-col items-center justify-center rounded-lg border border-dashed border-border">
          <p className="text-lg font-medium text-muted-foreground">
            No experiments found
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            Create your first experiment to get started
          </p>
          <button
            onClick={() => navigate('/experiments/new')}
            className="mt-4 flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            New Experiment
          </button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {experiments.map((experiment) => (
            <ExperimentCard key={experiment.id} experiment={experiment} />
          ))}
        </div>
      )}

    </div>
  )
}
