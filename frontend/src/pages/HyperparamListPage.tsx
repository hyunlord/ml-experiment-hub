import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CheckCircle2,
  Loader2,
  Plus,
  Search,
  Trophy,
  XCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import * as studiesApi from '@/api/studies'
import type { StudySummary } from '@/api/studies'

export default function HyperparamListPage() {
  const navigate = useNavigate()
  const [studies, setStudies] = useState<StudySummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    studiesApi
      .listStudies()
      .then(setStudies)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const statusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-destructive" />
      default:
        return <Search className="h-4 w-4 text-muted-foreground" />
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">Hyperparameter Search</h1>
        <button
          onClick={() => navigate('/hyperparam/new')}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Search
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : studies.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <Search className="mx-auto mb-3 h-10 w-10 text-muted-foreground/50" />
          <p className="text-sm text-muted-foreground">
            No studies yet. Start a new hyperparameter search.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {studies.map((study) => (
            <button
              key={study.id}
              onClick={() => navigate(`/hyperparam/${study.id}`)}
              className="flex w-full items-center gap-4 rounded-lg border border-border bg-card p-4 text-left transition-colors hover:bg-accent/50"
            >
              <div className="flex-shrink-0">{statusIcon(study.status)}</div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-card-foreground">{study.name}</p>
                <p className="text-xs text-muted-foreground">
                  {study.n_trials} trials | {study.objective_metric} ({study.direction})
                </p>
              </div>
              {study.best_value != null && (
                <div className="flex items-center gap-1.5 text-sm">
                  <Trophy className="h-4 w-4 text-yellow-500" />
                  <span className="font-mono text-foreground">{study.best_value.toFixed(6)}</span>
                </div>
              )}
              <span
                className={cn(
                  'rounded-full px-2 py-0.5 text-xs font-medium',
                  study.status === 'running' && 'bg-blue-500/10 text-blue-500',
                  study.status === 'completed' && 'bg-green-500/10 text-green-500',
                  study.status === 'failed' && 'bg-destructive/10 text-destructive',
                  study.status === 'pending' && 'bg-yellow-500/10 text-yellow-600',
                  study.status === 'cancelled' && 'bg-muted text-muted-foreground',
                )}
              >
                {study.status}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
