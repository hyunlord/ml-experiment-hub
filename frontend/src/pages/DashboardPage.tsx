import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  CheckCircle2,
  Clock,
  FlaskConical,
  Play,
  Plus,
  XCircle,
} from 'lucide-react'
import { useExperimentStore } from '@/stores/experimentStore'
import { formatRelativeTime, formatAbsoluteTime } from '@/utils/time'
import { ExperimentStatus } from '@/types/experiment'

export default function DashboardPage() {
  const navigate = useNavigate()
  const { experiments, loading, fetchExperiments } = useExperimentStore()

  useEffect(() => {
    fetchExperiments()
  }, [fetchExperiments])

  const running = experiments.filter((e) => e.status === ExperimentStatus.RUNNING)
  const completed = experiments.filter((e) => e.status === ExperimentStatus.COMPLETED)
  const failed = experiments.filter((e) => e.status === ExperimentStatus.FAILED)
  const pending = experiments.filter((e) => e.status === ExperimentStatus.DRAFT || e.status === ExperimentStatus.QUEUED)

  const recentCompleted = completed
    .sort(
      (a, b) =>
        new Date(b.updated_at ?? b.created_at).getTime() -
        new Date(a.updated_at ?? a.created_at).getTime(),
    )
    .slice(0, 5)

  if (loading && experiments.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading dashboard...</p>
      </div>
    )
  }

  return (
    <div>
      {/* Stats cards */}
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Experiments"
          value={experiments.length}
          icon={<FlaskConical className="h-5 w-5" />}
          color="text-primary"
        />
        <StatCard
          label="Running"
          value={running.length}
          icon={<Play className="h-5 w-5" />}
          color="text-green-500"
          onClick={() => navigate('/running')}
        />
        <StatCard
          label="Completed"
          value={completed.length}
          icon={<CheckCircle2 className="h-5 w-5" />}
          color="text-blue-500"
        />
        <StatCard
          label="Failed"
          value={failed.length}
          icon={<XCircle className="h-5 w-5" />}
          color="text-red-500"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Running experiments */}
        <section className="rounded-lg border border-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold text-card-foreground">
              <Activity className="h-4 w-4 text-green-500" />
              Running Now
            </h2>
            {running.length > 0 && (
              <button
                onClick={() => navigate('/running')}
                className="text-xs text-primary hover:underline"
              >
                View all
              </button>
            )}
          </div>

          {running.length === 0 ? (
            <div className="flex flex-col items-center py-8 text-center">
              <Clock className="mb-2 h-8 w-8 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">
                No experiments running
              </p>
              <button
                onClick={() => navigate('/experiments/new')}
                className="mt-3 flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
              >
                <Plus className="h-3 w-3" />
                Start one
              </button>
            </div>
          ) : (
            <ul className="space-y-2">
              {running.map((exp) => (
                <li
                  key={exp.id}
                  onClick={() => navigate(`/experiments/${exp.id}`)}
                  className="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex h-2 w-2 rounded-full bg-green-500" />
                    <span className="font-medium text-card-foreground">
                      {exp.name}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {exp.tags?.[0] ?? ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Recently completed */}
        <section className="rounded-lg border border-border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold text-card-foreground">
              <CheckCircle2 className="h-4 w-4 text-blue-500" />
              Recently Completed
            </h2>
            {completed.length > 0 && (
              <button
                onClick={() => navigate('/experiments')}
                className="text-xs text-primary hover:underline"
              >
                View all
              </button>
            )}
          </div>

          {recentCompleted.length === 0 ? (
            <div className="flex flex-col items-center py-8 text-center">
              <FlaskConical className="mb-2 h-8 w-8 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">
                No completed experiments yet
              </p>
            </div>
          ) : (
            <ul className="space-y-2">
              {recentCompleted.map((exp) => (
                <li
                  key={exp.id}
                  onClick={() => navigate(`/experiments/${exp.id}`)}
                  className="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent"
                >
                  <span className="font-medium text-card-foreground">
                    {exp.name}
                  </span>
                  <span className="text-xs text-muted-foreground" title={formatAbsoluteTime(exp.updated_at ?? exp.created_at)}>
                    {formatRelativeTime(exp.updated_at ?? exp.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* Pending / queued */}
      {pending.length > 0 && (
        <section className="mt-6 rounded-lg border border-border bg-card p-5">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-card-foreground">
            <Clock className="h-4 w-4 text-yellow-500" />
            Queued ({pending.length})
          </h2>
          <ul className="space-y-2">
            {pending.slice(0, 10).map((exp) => (
              <li
                key={exp.id}
                onClick={() => navigate(`/experiments/${exp.id}`)}
                className="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent"
              >
                <span className="font-medium text-card-foreground">
                  {exp.name}
                </span>
                <span className="text-xs text-muted-foreground">
                  {exp.status}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// StatCard
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  icon,
  color,
  onClick,
}: {
  label: string
  value: number
  icon: React.ReactNode
  color: string
  onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={`rounded-lg border border-border bg-card p-4 ${
        onClick ? 'cursor-pointer transition-colors hover:bg-accent' : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className={color}>{icon}</span>
      </div>
      <p className="mt-2 text-3xl font-bold text-card-foreground">{value}</p>
    </div>
  )
}
