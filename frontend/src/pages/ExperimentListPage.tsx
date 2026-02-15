import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Copy,
  ListPlus,
  Pencil,
  Play,
  Plus,
  Search,
  Square,
  Trash2,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import client from '@/api/client'
import { addToQueue } from '@/api/queue'
import { formatRelativeTime, formatAbsoluteTime } from '@/utils/time'

// ---------------------------------------------------------------------------
// Types (aligned with new backend ExperimentResponse)
// ---------------------------------------------------------------------------

type ExperimentStatus = 'draft' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

interface ExperimentRow {
  id: number
  name: string
  description: string
  status: ExperimentStatus
  config: Record<string, unknown>
  schema_id: number | null
  tags: string[]
  created_at: string
  updated_at: string
  // Enriched client-side
  best_metric?: number | null
  progress?: string | null // e.g. "epoch 3/30"
}

type SortKey = 'id' | 'name' | 'created_at' | 'best_metric'
type SortDir = 'asc' | 'desc'

const STATUS_CONFIG: Record<ExperimentStatus, { icon: string; label: string; classes: string }> = {
  draft: { icon: '○', label: 'Draft', classes: 'text-muted-foreground' },
  queued: { icon: '◌', label: 'Queued', classes: 'text-muted-foreground' },
  running: { icon: '●', label: 'Running', classes: 'text-blue-500' },
  completed: { icon: '✓', label: 'Done', classes: 'text-green-500' },
  failed: { icon: '✗', label: 'Failed', classes: 'text-destructive' },
  cancelled: { icon: '—', label: 'Cancelled', classes: 'text-muted-foreground' },
}

const ALL_STATUSES: ExperimentStatus[] = ['draft', 'queued', 'running', 'completed', 'failed', 'cancelled']

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ExperimentListPage() {
  const navigate = useNavigate()

  // ── Data ──────────────────────────────────────────────────────────
  const [experiments, setExperiments] = useState<ExperimentRow[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  // ── Filters ───────────────────────────────────────────────────────
  const [statusFilter, setStatusFilter] = useState<ExperimentStatus | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])

  // ── Sorting ───────────────────────────────────────────────────────
  const [sortKey, setSortKey] = useState<SortKey>('id')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  // ── Selection (for compare) ───────────────────────────────────────
  const [selected, setSelected] = useState<Set<number>>(new Set())

  // ── Pagination ────────────────────────────────────────────────────
  const [page, setPage] = useState(0)
  const pageSize = 20

  // ── All available tags ────────────────────────────────────────────
  const allTags = useMemo(() => {
    const tagSet = new Set<string>()
    experiments.forEach((exp) => exp.tags.forEach((t) => tagSet.add(t)))
    return Array.from(tagSet).sort()
  }, [experiments])

  // ── Fetch experiments ─────────────────────────────────────────────
  const fetchExperiments = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = {
        skip: page * pageSize,
        limit: pageSize,
      }
      if (statusFilter !== 'all') params.status = statusFilter

      const res = await client.get('/experiments', { params })
      const data = res.data
      setExperiments(data.experiments || [])
      setTotal(data.total || 0)
    } catch {
      // Silently handle fetch errors
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter])

  useEffect(() => {
    fetchExperiments()
  }, [fetchExperiments])

  // ── Client-side filter + sort ─────────────────────────────────────
  const filteredExperiments = useMemo(() => {
    let result = [...experiments]

    // Search filter (client-side on name)
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter((exp) => exp.name.toLowerCase().includes(q))
    }

    // Tag filter (client-side AND logic)
    if (selectedTags.length > 0) {
      result = result.filter((exp) =>
        selectedTags.every((tag) => exp.tags.includes(tag)),
      )
    }

    // Sort
    result.sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'id':
          cmp = a.id - b.id
          break
        case 'name':
          cmp = a.name.localeCompare(b.name)
          break
        case 'created_at':
          cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
          break
        case 'best_metric':
          cmp = (a.best_metric ?? -1) - (b.best_metric ?? -1)
          break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })

    return result
  }, [experiments, searchQuery, selectedTags, sortKey, sortDir])

  // ── Sort handler ──────────────────────────────────────────────────
  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  // ── Selection handlers ────────────────────────────────────────────
  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else if (next.size < 3) {
        next.add(id)
      }
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selected.size === filteredExperiments.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(filteredExperiments.slice(0, 3).map((e) => e.id)))
    }
  }

  // ── Tag filter toggle ─────────────────────────────────────────────
  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    )
  }

  // ── Actions ───────────────────────────────────────────────────────
  const handleClone = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    try {
      const res = await client.post(`/experiments/${id}/clone`)
      navigate(`/experiments/new?clone=${res.data.id}`)
    } catch {
      // Could show toast
    }
  }

  const handleStart = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    try {
      await client.post(`/experiments/${id}/start`)
      fetchExperiments()
    } catch {
      // Could show toast
    }
  }

  const handleStop = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    try {
      await client.post(`/experiments/${id}/stop`)
      fetchExperiments()
    } catch {
      // Could show toast
    }
  }

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    if (!confirm('Delete this experiment?')) return
    try {
      await client.delete(`/experiments/${id}`)
      setSelected((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      fetchExperiments()
    } catch {
      // Could show toast
    }
  }

  const handleAddToQueue = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    try {
      await addToQueue(id)
      fetchExperiments()
    } catch {
      // Could show toast
    }
  }

  const handleMonitor = (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    navigate(`/experiments/${id}`)
  }

  // ── Pagination ────────────────────────────────────────────────────
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  // ── Sort icon helper ──────────────────────────────────────────────
  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col)
      return <ArrowUpDown className="ml-1 inline-block h-3.5 w-3.5 text-muted-foreground/50" />
    return sortDir === 'asc' ? (
      <ArrowUp className="ml-1 inline-block h-3.5 w-3.5" />
    ) : (
      <ArrowDown className="ml-1 inline-block h-3.5 w-3.5" />
    )
  }

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Experiments</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {total} experiment{total !== 1 ? 's' : ''} total
          </p>
        </div>
        <button
          onClick={() => navigate('/experiments/new')}
          className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New
        </button>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as ExperimentStatus | 'all')
            setPage(0)
          }}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All Status</option>
          {ALL_STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_CONFIG[s].label}
            </option>
          ))}
        </select>

        {/* Tag chips */}
        {allTags.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            {allTags.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag)}
                className={cn(
                  'rounded-md border px-2.5 py-1 text-xs transition-colors',
                  selectedTags.includes(tag)
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-input bg-background text-muted-foreground hover:bg-accent',
                )}
              >
                {tag}
              </button>
            ))}
            {selectedTags.length > 0 && (
              <button
                type="button"
                onClick={() => setSelectedTags([])}
                className="rounded-md p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        )}

        {/* Search */}
        <div className="relative ml-auto">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search..."
            className="rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      {/* Compare bar */}
      {selected.size >= 2 && (
        <div className="mb-4 flex items-center gap-3 rounded-md border border-primary/30 bg-primary/5 px-4 py-2">
          <span className="text-sm text-foreground">
            {selected.size} selected
          </span>
          <button
            onClick={() => {
              const ids = Array.from(selected).join(',')
              navigate(`/experiments/compare?ids=${ids}`)
            }}
            className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Compare
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Clear
          </button>
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-border">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                {/* Checkbox */}
                <th className="w-10 px-3 py-3">
                  <input
                    type="checkbox"
                    checked={
                      filteredExperiments.length > 0 &&
                      selected.size === Math.min(filteredExperiments.length, 3)
                    }
                    onChange={toggleSelectAll}
                    className="h-4 w-4 rounded border-input accent-primary"
                  />
                </th>
                {/* # */}
                <th className="w-14 px-3 py-3 text-left">
                  <button
                    onClick={() => handleSort('id')}
                    className="inline-flex items-center font-semibold text-muted-foreground hover:text-foreground"
                  >
                    #
                    <SortIcon col="id" />
                  </button>
                </th>
                {/* Name */}
                <th className="px-3 py-3 text-left">
                  <button
                    onClick={() => handleSort('name')}
                    className="inline-flex items-center font-semibold text-muted-foreground hover:text-foreground"
                  >
                    Name
                    <SortIcon col="name" />
                  </button>
                </th>
                {/* Status */}
                <th className="w-28 px-3 py-3 text-left font-semibold text-muted-foreground">
                  Status
                </th>
                {/* Tags */}
                <th className="w-40 px-3 py-3 text-left font-semibold text-muted-foreground">
                  Tags
                </th>
                {/* Best mAP */}
                <th className="w-24 px-3 py-3 text-left">
                  <button
                    onClick={() => handleSort('best_metric')}
                    className="inline-flex items-center font-semibold text-muted-foreground hover:text-foreground"
                  >
                    Best Metric
                    <SortIcon col="best_metric" />
                  </button>
                </th>
                {/* Date */}
                <th className="w-28 px-3 py-3 text-left">
                  <button
                    onClick={() => handleSort('created_at')}
                    className="inline-flex items-center font-semibold text-muted-foreground hover:text-foreground"
                  >
                    Created
                    <SortIcon col="created_at" />
                  </button>
                </th>
                {/* Actions */}
                <th className="w-36 px-3 py-3 text-right font-semibold text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-muted-foreground">
                    Loading experiments...
                  </td>
                </tr>
              ) : filteredExperiments.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center">
                    <p className="text-muted-foreground">No experiments found</p>
                    <button
                      onClick={() => navigate('/experiments/new')}
                      className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Create first experiment
                    </button>
                  </td>
                </tr>
              ) : (
                filteredExperiments.map((exp) => {
                  const statusCfg = STATUS_CONFIG[exp.status] || STATUS_CONFIG.draft
                  const isRunning = exp.status === 'running'
                  const isDraft = exp.status === 'draft'
                  const canStart = isDraft || exp.status === 'failed' || exp.status === 'cancelled'
                  const isSelected = selected.has(exp.id)

                  return (
                    <tr
                      key={exp.id}
                      onClick={() => navigate(`/experiments/${exp.id}`)}
                      className={cn(
                        'cursor-pointer border-b border-border transition-colors hover:bg-accent/50',
                        isSelected && 'bg-primary/5',
                      )}
                    >
                      {/* Checkbox */}
                      <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(exp.id)}
                          disabled={!isSelected && selected.size >= 3}
                          className="h-4 w-4 rounded border-input accent-primary disabled:opacity-30"
                        />
                      </td>
                      {/* # */}
                      <td className="px-3 py-3 font-mono text-xs text-muted-foreground">
                        {exp.id}
                      </td>
                      {/* Name */}
                      <td className="px-3 py-3">
                        <div className="font-medium text-foreground">{exp.name}</div>
                        {exp.description && (
                          <div className="mt-0.5 truncate text-xs text-muted-foreground">
                            {exp.description}
                          </div>
                        )}
                      </td>
                      {/* Status */}
                      <td className="px-3 py-3">
                        <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', statusCfg.classes)}>
                          <span>{statusCfg.icon}</span>
                          {statusCfg.label}
                        </span>
                        {isRunning && exp.progress && (
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            {exp.progress}
                          </div>
                        )}
                      </td>
                      {/* Tags */}
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-1">
                          {exp.tags.slice(0, 3).map((tag) => (
                            <span
                              key={tag}
                              className="rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground"
                            >
                              {tag}
                            </span>
                          ))}
                          {exp.tags.length > 3 && (
                            <span className="text-xs text-muted-foreground">
                              +{exp.tags.length - 3}
                            </span>
                          )}
                        </div>
                      </td>
                      {/* Best mAP */}
                      <td className="px-3 py-3 font-mono text-xs">
                        {exp.best_metric != null ? (
                          <span className="text-foreground">{exp.best_metric.toFixed(3)}</span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      {/* Date */}
                      <td className="px-3 py-3 text-xs text-muted-foreground">
                        <span title={formatAbsoluteTime(exp.created_at)}>{formatRelativeTime(exp.created_at)}</span>
                      </td>
                      {/* Actions */}
                      <td className="px-3 py-3">
                        <div className="flex items-center justify-end gap-1">
                          {/* Monitor (not for draft) */}
                          {!isDraft && (
                            <ActionBtn
                              title="Monitor"
                              onClick={(e) => handleMonitor(e, exp.id)}
                            >
                              <BarChart3 className="h-4 w-4" />
                            </ActionBtn>
                          )}
                          {/* Edit (draft only) */}
                          {isDraft && (
                            <ActionBtn
                              title="Edit"
                              onClick={(e) => {
                                e.stopPropagation()
                                navigate(`/experiments/${exp.id}/edit`)
                              }}
                            >
                              <Pencil className="h-4 w-4" />
                            </ActionBtn>
                          )}
                          {/* Clone */}
                          <ActionBtn
                            title="Clone"
                            onClick={(e) => handleClone(e, exp.id)}
                          >
                            <Copy className="h-4 w-4" />
                          </ActionBtn>
                          {/* Add to Queue (draft/failed/cancelled/completed) */}
                          {(canStart || exp.status === 'completed') && (
                            <ActionBtn
                              title="Add to Queue"
                              onClick={(e) => handleAddToQueue(e, exp.id)}
                              className="text-primary hover:bg-primary/10"
                            >
                              <ListPlus className="h-4 w-4" />
                            </ActionBtn>
                          )}
                          {/* Start (draft/failed/cancelled) */}
                          {canStart && (
                            <ActionBtn
                              title="Start"
                              onClick={(e) => handleStart(e, exp.id)}
                              className="text-green-500 hover:bg-green-500/10"
                            >
                              <Play className="h-4 w-4" />
                            </ActionBtn>
                          )}
                          {/* Stop (running) */}
                          {isRunning && (
                            <ActionBtn
                              title="Stop"
                              onClick={(e) => handleStop(e, exp.id)}
                              className="text-orange-500 hover:bg-orange-500/10"
                            >
                              <Square className="h-4 w-4" />
                            </ActionBtn>
                          )}
                          {/* Delete */}
                          <ActionBtn
                            title="Delete"
                            onClick={(e) => handleDelete(e, exp.id)}
                            className="text-destructive hover:bg-destructive/10"
                          >
                            <Trash2 className="h-4 w-4" />
                          </ActionBtn>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <span className="text-xs text-muted-foreground">
              Page {page + 1} of {totalPages}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-30"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-30"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ActionBtn({
  children,
  title,
  onClick,
  className,
}: {
  children: React.ReactNode
  title: string
  onClick: (e: React.MouseEvent) => void
  className?: string
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={cn(
        'rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
        className,
      )}
    >
      {children}
    </button>
  )
}
