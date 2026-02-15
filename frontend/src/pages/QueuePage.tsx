import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  Clock,
  GripVertical,
  ListOrdered,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react'
import {
  listQueue,
  removeFromQueue,
  reorderQueue,
  queueHistory,
  addToQueue,
  type QueueEntry,
} from '@/api/queue'
import { cn } from '@/lib/utils'
import client from '@/api/client'
import { formatAbsoluteTime } from '@/utils/time'

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  string,
  { icon: string; label: string; classes: string }
> = {
  waiting: { icon: '\u23F3', label: 'Waiting', classes: 'text-muted-foreground' },
  running: { icon: '\uD83D\uDD04', label: 'Running', classes: 'text-blue-500' },
  completed: { icon: '\u2705', label: 'Completed', classes: 'text-green-500' },
  failed: { icon: '\u274C', label: 'Failed', classes: 'text-destructive' },
  cancelled: { icon: '\u2014', label: 'Cancelled', classes: 'text-muted-foreground' },
}

// ---------------------------------------------------------------------------
// Experiment picker (simple modal)
// ---------------------------------------------------------------------------

interface Experiment {
  id: number
  name: string
  status: string
}

function AddToQueueModal({
  open,
  onClose,
  onAdd,
}: {
  open: boolean
  onClose: () => void
  onAdd: (id: number) => void
}) {
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    client
      .get('/api/experiments')
      .then((r) => setExperiments(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-card-foreground">
            Add to Queue
          </h3>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : (
          <div className="max-h-64 space-y-1 overflow-y-auto">
            {experiments
              .filter((e) => e.status === 'draft' || e.status === 'completed' || e.status === 'failed')
              .map((exp) => (
                <button
                  key={exp.id}
                  onClick={() => {
                    onAdd(exp.id)
                    onClose()
                  }}
                  className="flex w-full items-center justify-between rounded-md px-3 py-2 text-sm text-card-foreground hover:bg-accent"
                >
                  <span className="truncate">{exp.name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    #{exp.id}
                  </span>
                </button>
              ))}
            {experiments.filter(
              (e) => e.status === 'draft' || e.status === 'completed' || e.status === 'failed'
            ).length === 0 && (
              <p className="text-sm text-muted-foreground">
                No experiments available to queue.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sortable queue item
// ---------------------------------------------------------------------------

function SortableQueueItem({
  entry,
  onRemove,
  onNavigate,
}: {
  entry: QueueEntry
  onRemove: (id: number) => void
  onNavigate: (runId: number) => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: entry.id, disabled: entry.status !== 'waiting' })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const st = STATUS_CONFIG[entry.status] || STATUS_CONFIG.waiting

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3',
        isDragging && 'z-10 shadow-lg opacity-80',
        entry.status === 'running' && 'border-blue-500/40'
      )}
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        className={cn(
          'cursor-grab text-muted-foreground',
          entry.status !== 'waiting' && 'cursor-not-allowed opacity-30'
        )}
        disabled={entry.status !== 'waiting'}
      >
        <GripVertical className="h-4 w-4" />
      </button>

      {/* Position */}
      <span className="w-6 text-center text-xs font-mono text-muted-foreground">
        {entry.position + 1}
      </span>

      {/* Status */}
      <span className={cn('text-sm', st.classes)} title={st.label}>
        {st.icon}
      </span>

      {/* Experiment name */}
      <div className="flex-1 min-w-0">
        <p className="truncate text-sm font-medium text-card-foreground">
          {entry.experiment_name}
        </p>
        <p className="text-xs text-muted-foreground">
          Added {formatAbsoluteTime(entry.added_at)}
          {entry.started_at && (
            <> &middot; Started {formatAbsoluteTime(entry.started_at)}</>
          )}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        {entry.run_id && (
          <button
            onClick={() => onNavigate(entry.run_id!)}
            className="rounded-md px-2 py-1 text-xs text-primary hover:bg-primary/10"
          >
            Run #{entry.run_id}
          </button>
        )}
        {entry.status === 'waiting' && (
          <button
            onClick={() => onRemove(entry.id)}
            className="rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            title="Remove from queue"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function QueuePage() {
  const navigate = useNavigate()
  const [entries, setEntries] = useState<QueueEntry[]>([])
  const [history, setHistory] = useState<QueueEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const fetchQueue = useCallback(async () => {
    try {
      const data = await listQueue()
      setEntries(data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const data = await queueHistory()
      setHistory(data)
    } catch {
      // ignore
    }
  }, [])

  // Poll queue every 3 seconds
  useEffect(() => {
    fetchQueue()
    const interval = setInterval(fetchQueue, 3000)
    return () => clearInterval(interval)
  }, [fetchQueue])

  useEffect(() => {
    if (showHistory) fetchHistory()
  }, [showHistory, fetchHistory])

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = entries.findIndex((e) => e.id === active.id)
    const newIndex = entries.findIndex((e) => e.id === over.id)
    const reordered = arrayMove(entries, oldIndex, newIndex)
    setEntries(reordered)

    // Persist new order
    const waitingIds = reordered
      .filter((e) => e.status === 'waiting')
      .map((e) => e.id)
    await reorderQueue(waitingIds)
    fetchQueue()
  }

  const handleRemove = async (id: number) => {
    await removeFromQueue(id)
    fetchQueue()
  }

  const handleAdd = async (experimentId: number) => {
    await addToQueue(experimentId)
    fetchQueue()
  }

  const waitingEntries = entries.filter((e) => e.status === 'waiting')
  const runningEntries = entries.filter((e) => e.status === 'running')

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ListOrdered className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold text-foreground">
            Experiment Queue
          </h2>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            {waitingEntries.length} waiting
          </span>
          {runningEntries.length > 0 && (
            <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-500">
              {runningEntries.length} running
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              showHistory
                ? 'bg-accent text-foreground'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground'
            )}
          >
            <Clock className="h-3.5 w-3.5" />
            History
          </button>
          <button
            onClick={fetchQueue}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-3.5 w-3.5" />
            Add
          </button>
        </div>
      </div>

      {/* Running entries (not draggable) */}
      {runningEntries.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">
            Currently Running
          </h3>
          {runningEntries.map((entry) => (
            <SortableQueueItem
              key={entry.id}
              entry={entry}
              onRemove={handleRemove}
              onNavigate={(runId) => navigate(`/runs/${runId}`)}
            />
          ))}
        </div>
      )}

      {/* Waiting entries (draggable) */}
      <div className="space-y-2">
        {waitingEntries.length > 0 && (
          <h3 className="text-sm font-medium text-muted-foreground">
            Up Next (drag to reorder)
          </h3>
        )}
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={waitingEntries.map((e) => e.id)}
            strategy={verticalListSortingStrategy}
          >
            {waitingEntries.map((entry) => (
              <SortableQueueItem
                key={entry.id}
                entry={entry}
                onRemove={handleRemove}
                onNavigate={(runId) => navigate(`/runs/${runId}`)}
              />
            ))}
          </SortableContext>
        </DndContext>
      </div>

      {/* Empty state */}
      {!loading && entries.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border py-12">
          <ListOrdered className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Queue is empty. Add experiments to run them sequentially.
          </p>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Experiment
          </button>
        </div>
      )}

      {/* History */}
      {showHistory && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">
            Queue History
          </h3>
          {history.length === 0 ? (
            <p className="text-sm text-muted-foreground">No history yet.</p>
          ) : (
            history.map((entry) => {
              const st = STATUS_CONFIG[entry.status] || STATUS_CONFIG.waiting
              return (
                <div
                  key={entry.id}
                  className="flex items-center gap-3 rounded-lg border border-border bg-card/50 px-4 py-2.5"
                >
                  <span className={cn('text-sm', st.classes)}>{st.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="truncate text-sm text-card-foreground">
                      {entry.experiment_name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {entry.completed_at &&
                        formatAbsoluteTime(entry.completed_at)}
                      {entry.error_message && (
                        <span className="ml-1 text-destructive">
                          — {entry.error_message}
                        </span>
                      )}
                    </p>
                  </div>
                  {entry.run_id && (
                    <button
                      onClick={() => navigate(`/runs/${entry.run_id}`)}
                      className="text-xs text-primary hover:underline"
                    >
                      Run #{entry.run_id}
                    </button>
                  )}
                </div>
              )
            })
          )}
        </div>
      )}

      {/* Add modal */}
      <AddToQueueModal
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onAdd={handleAdd}
      />
    </div>
  )
}
