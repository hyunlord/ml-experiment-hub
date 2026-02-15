import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, ExternalLink } from 'lucide-react'
import { useExperimentStore } from '@/stores/experimentStore'
import { ExperimentStatus } from '@/types/experiment'
import StatusBadge from '@/components/StatusBadge'
import { formatAbsoluteTime } from '@/utils/time'

export default function RunningPage() {
  const navigate = useNavigate()
  const { experiments, loading, fetchExperiments } = useExperimentStore()

  useEffect(() => {
    fetchExperiments({ status: ExperimentStatus.RUNNING })
  }, [fetchExperiments])

  const running = experiments.filter((e) => e.status === ExperimentStatus.RUNNING)

  if (loading && experiments.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    )
  }

  if (running.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center">
        <Activity className="mb-3 h-12 w-12 text-muted-foreground/40" />
        <p className="text-lg font-medium text-muted-foreground">
          No experiments running
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          Start an experiment from the Experiments page
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {running.map((exp) => (
        <div
          key={exp.id}
          className="flex items-center justify-between rounded-lg border border-border bg-card p-4 transition-colors hover:bg-accent"
        >
          <div className="flex items-center gap-3">
            <span className="flex h-2.5 w-2.5 animate-pulse rounded-full bg-green-500" />
            <div>
              <p className="font-medium text-card-foreground">{exp.name}</p>
              <p className="text-xs text-muted-foreground">
                {exp.tags?.[0] ?? ''} &middot; Updated{' '}
                {formatAbsoluteTime(exp.updated_at)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={exp.status} />
            <button
              onClick={() => navigate(`/experiments/${exp.id}`)}
              className="flex items-center gap-1 text-xs text-primary hover:underline"
            >
              <ExternalLink className="h-3 w-3" />
              Detail
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
