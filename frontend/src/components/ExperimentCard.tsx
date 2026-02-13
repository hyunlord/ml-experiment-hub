import { Link } from 'react-router-dom'
import type { Experiment } from '@/types/experiment'
import StatusBadge from './StatusBadge'
import { Clock, Calendar } from 'lucide-react'

interface ExperimentCardProps {
  experiment: Experiment
}

export default function ExperimentCard({ experiment }: ExperimentCardProps) {
  return (
    <Link
      to={`/experiments/${experiment.id}`}
      className="block rounded-lg border border-border bg-card p-6 transition-colors hover:bg-accent"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-card-foreground">
            {experiment.name}
          </h3>
          {experiment.description && (
            <p className="mt-1 text-sm text-muted-foreground">
              {experiment.description}
            </p>
          )}
        </div>
        <StatusBadge status={experiment.status} />
      </div>
      <div className="mt-4 flex items-center gap-4 text-sm text-muted-foreground">
        <span className="rounded bg-secondary px-2 py-1 text-secondary-foreground">
          {experiment.framework}
        </span>
        <div className="flex items-center gap-1">
          <Calendar className="h-4 w-4" />
          <span>
            {new Date(experiment.created_at).toLocaleDateString()}
          </span>
        </div>
        {experiment.started_at && (
          <div className="flex items-center gap-1">
            <Clock className="h-4 w-4" />
            <span>
              {new Date(experiment.started_at).toLocaleTimeString()}
            </span>
          </div>
        )}
      </div>
    </Link>
  )
}
