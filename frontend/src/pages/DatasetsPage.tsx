import { useCallback, useEffect, useState } from 'react'
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Loader2,
  Eye,
  Play,
  Database,
  HardDrive,
  FileText,
  X,
} from 'lucide-react'
import type { Dataset, DatasetStatus, PreviewResponse } from '@/api/datasets'
import { listDatasets, previewDataset, prepareDataset } from '@/api/datasets'

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  DatasetStatus,
  { icon: React.ReactNode; label: string; className: string }
> = {
  ready: {
    icon: <CheckCircle className="h-4 w-4" />,
    label: 'Ready',
    className: 'text-green-600 dark:text-green-400 bg-green-500/10',
  },
  raw_only: {
    icon: <AlertTriangle className="h-4 w-4" />,
    label: 'Raw Only',
    className: 'text-amber-600 dark:text-amber-400 bg-amber-500/10',
  },
  not_found: {
    icon: <XCircle className="h-4 w-4" />,
    label: 'Not Found',
    className: 'text-red-600 dark:text-red-400 bg-red-500/10',
  },
  preparing: {
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    label: 'Preparing',
    className: 'text-blue-600 dark:text-blue-400 bg-blue-500/10',
  },
}

function StatusBadge({ status }: { status: DatasetStatus }) {
  const cfg = STATUS_CONFIG[status]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${cfg.className}`}
    >
      {cfg.icon}
      {cfg.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Format bytes
// ---------------------------------------------------------------------------

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

// ---------------------------------------------------------------------------
// Language bar
// ---------------------------------------------------------------------------

function LanguageBar({ stats }: { stats: Record<string, number> }) {
  const total = Object.values(stats).reduce((a, b) => a + b, 0)
  if (total === 0) return null

  const colors: Record<string, string> = {
    ko: 'bg-blue-500',
    en: 'bg-green-500',
    mixed: 'bg-amber-500',
    unknown: 'bg-gray-400',
  }

  return (
    <div className="space-y-1.5">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
        {Object.entries(stats).map(([lang, count]) => (
          <div
            key={lang}
            className={`${colors[lang] || 'bg-gray-400'} transition-all`}
            style={{ width: `${(count / total) * 100}%` }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        {Object.entries(stats).map(([lang, count]) => (
          <span key={lang} className="flex items-center gap-1">
            <span className={`inline-block h-2 w-2 rounded-full ${colors[lang] || 'bg-gray-400'}`} />
            {lang.toUpperCase()}: {count} ({((count / total) * 100).toFixed(0)}%)
          </span>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Preview modal
// ---------------------------------------------------------------------------

function PreviewModal({
  preview,
  onClose,
}: {
  preview: PreviewResponse
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-lg border border-border bg-card shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <div>
            <h3 className="text-lg font-semibold text-card-foreground">
              {preview.dataset_name} Preview
            </h3>
            <p className="text-sm text-muted-foreground">
              {preview.total_entries != null
                ? `${preview.total_entries.toLocaleString()} total entries`
                : 'Unknown entries'}
              {' | '}Showing {preview.samples.length} random samples
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Language stats */}
        {Object.keys(preview.language_stats).length > 0 && (
          <div className="border-b border-border px-5 py-3">
            <p className="mb-2 text-xs font-medium uppercase text-muted-foreground">
              Language Distribution (sampled)
            </p>
            <LanguageBar stats={preview.language_stats} />
          </div>
        )}

        {/* Samples */}
        <div className="divide-y divide-border">
          {preview.samples.map((sample, idx) => (
            <div key={idx} className="flex gap-4 px-5 py-4">
              {/* Thumbnail */}
              <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border bg-muted">
                {sample._image_exists && sample._image_url ? (
                  <img
                    src={`http://localhost:8002${sample._image_url}`}
                    alt=""
                    className="h-full w-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none'
                    }}
                  />
                ) : (
                  <FileText className="h-6 w-6 text-muted-foreground" />
                )}
              </div>

              {/* Caption(s) */}
              <div className="min-w-0 flex-1 space-y-1">
                {sample.caption && (
                  <p className="text-sm text-card-foreground">
                    {sample.caption}
                    {sample._caption_lang && (
                      <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                        {sample._caption_lang.toUpperCase()}
                      </span>
                    )}
                  </p>
                )}
                {sample.caption_ko && sample.caption_ko !== sample.caption && (
                  <p className="text-sm text-muted-foreground">
                    {sample.caption_ko}
                    <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs">KO</span>
                  </p>
                )}
                {sample.caption_en && sample.caption_en !== sample.caption && (
                  <p className="text-sm text-muted-foreground">
                    {sample.caption_en}
                    <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs">EN</span>
                  </p>
                )}
                {sample.image && (
                  <p className="truncate text-xs text-muted-foreground/70">
                    {sample.image}
                    {sample.split && (
                      <span className="ml-2 rounded bg-muted px-1 py-0.5">
                        {sample.split}
                      </span>
                    )}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Dataset card
// ---------------------------------------------------------------------------

function DatasetCard({
  dataset,
  onPreview,
  onPrepare,
}: {
  dataset: Dataset
  onPreview: (id: number) => void
  onPrepare: (id: number) => void
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5 transition-shadow hover:shadow-md">
      {/* Header row */}
      <div className="mb-3 flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 shrink-0 text-primary" />
            <h3 className="truncate text-sm font-semibold text-card-foreground">
              {dataset.name}
            </h3>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{dataset.description}</p>
        </div>
        <StatusBadge status={dataset.status} />
      </div>

      {/* Stats row */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        <div className="rounded-md bg-muted/50 px-3 py-2">
          <p className="text-xs text-muted-foreground">Entries</p>
          <p className="text-sm font-medium text-card-foreground">
            {dataset.entry_count != null ? dataset.entry_count.toLocaleString() : '-'}
          </p>
        </div>
        <div className="rounded-md bg-muted/50 px-3 py-2">
          <p className="text-xs text-muted-foreground">Size</p>
          <p className="text-sm font-medium text-card-foreground">
            {formatBytes(dataset.size_bytes)}
          </p>
        </div>
        <div className="rounded-md bg-muted/50 px-3 py-2">
          <p className="text-xs text-muted-foreground">Format</p>
          <p className="text-sm font-medium text-card-foreground">
            {dataset.raw_format}
          </p>
        </div>
      </div>

      {/* Progress bar for preparing */}
      {dataset.status === 'preparing' && dataset.prepare_progress != null && (
        <div className="mb-4">
          <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
            <span>Preparing JSONL...</span>
            <span>{dataset.prepare_progress}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-blue-500 transition-all"
              style={{ width: `${dataset.prepare_progress}%` }}
            />
          </div>
        </div>
      )}

      {/* File paths */}
      <div className="mb-4 space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <HardDrive className="h-3 w-3" />
          <span className="truncate">
            {dataset.data_root || '-'} / {dataset.jsonl_path || '-'}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {dataset.status === 'ready' && (
          <button
            onClick={() => onPreview(dataset.id)}
            className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
          >
            <Eye className="h-3.5 w-3.5" />
            Preview
          </button>
        )}
        {dataset.status === 'raw_only' && (
          <button
            onClick={() => onPrepare(dataset.id)}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Play className="h-3.5 w-3.5" />
            Prepare JSONL
          </button>
        )}
        {dataset.status === 'not_found' && (
          <span className="text-xs text-muted-foreground">
            Data not available on this machine
          </span>
        )}
        {dataset.status === 'preparing' && (
          <span className="text-xs text-muted-foreground">
            Preparation in progress...
          </span>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<PreviewResponse | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const fetchDatasets = useCallback(async () => {
    try {
      const data = await listDatasets()
      setDatasets(data)
      setError('')
    } catch {
      setError('Failed to load datasets')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDatasets()
  }, [fetchDatasets])

  // Poll while any dataset is preparing
  useEffect(() => {
    const hasPreparing = datasets.some((d) => d.status === 'preparing')
    if (!hasPreparing) return

    const interval = setInterval(fetchDatasets, 3000)
    return () => clearInterval(interval)
  }, [datasets, fetchDatasets])

  const handlePreview = async (id: number) => {
    setPreviewLoading(true)
    try {
      const data = await previewDataset(id)
      setPreview(data)
    } catch {
      setError('Failed to load preview')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handlePrepare = async (id: number) => {
    try {
      await prepareDataset(id)
      // Refresh to show preparing status
      fetchDatasets()
    } catch {
      setError('Failed to start prepare job')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const readyCount = datasets.filter((d) => d.status === 'ready').length
  const rawCount = datasets.filter((d) => d.status === 'raw_only').length
  const notFoundCount = datasets.filter((d) => d.status === 'not_found').length

  return (
    <div>
      {/* Summary bar */}
      <div className="mb-6 flex items-center gap-4">
        <div className="flex items-center gap-1.5 text-sm">
          <CheckCircle className="h-4 w-4 text-green-500" />
          <span className="text-muted-foreground">{readyCount} Ready</span>
        </div>
        <div className="flex items-center gap-1.5 text-sm">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          <span className="text-muted-foreground">{rawCount} Raw Only</span>
        </div>
        <div className="flex items-center gap-1.5 text-sm">
          <XCircle className="h-4 w-4 text-red-500" />
          <span className="text-muted-foreground">{notFoundCount} Not Found</span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Dataset grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {datasets.map((ds) => (
          <DatasetCard
            key={ds.id}
            dataset={ds}
            onPreview={handlePreview}
            onPrepare={handlePrepare}
          />
        ))}
      </div>

      {/* Empty state */}
      {datasets.length === 0 && (
        <div className="py-20 text-center text-muted-foreground">
          <Database className="mx-auto mb-3 h-10 w-10" />
          <p>No datasets registered</p>
        </div>
      )}

      {/* Preview loading indicator */}
      {previewLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <Loader2 className="h-10 w-10 animate-spin text-white" />
        </div>
      )}

      {/* Preview modal */}
      {preview && <PreviewModal preview={preview} onClose={() => setPreview(null)} />}
    </div>
  )
}
