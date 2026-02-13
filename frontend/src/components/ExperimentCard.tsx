import { Link } from 'react-router-dom'
import type { Experiment } from '@/types/experiment'
import StatusBadge from './StatusBadge'
import { Calendar } from 'lucide-react'

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
        {experiment.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {experiment.tags.map((tag) => (
              <span key={tag} className="rounded bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
                {tag}
              </span>
            ))}
          </div>
        )}
        <div className="flex items-center gap-1">
          <Calendar className="h-4 w-4" />
          <span>
            {new Date(experiment.created_at).toLocaleDateString()}
          </span>
        </div>
      </div>
    </Link>
  )
}
