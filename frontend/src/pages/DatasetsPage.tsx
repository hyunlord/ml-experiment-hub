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
  Plus,
  Trash2,
  Settings2,
  Search,
} from 'lucide-react'
import type {
  Dataset,
  DatasetStatus,
  DatasetType,
  DatasetFormat,
  SplitMethod,
  PreviewResponse,
  CreateDatasetPayload,
  DetectResult,
} from '@/api/datasets'
import {
  listDatasets,
  previewDataset,
  prepareDataset,
  createDataset,
  deleteDataset,
  detectDataset,
} from '@/api/datasets'

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
              {preview.dataset_type && (
                <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs">
                  {preview.dataset_type}
                </span>
              )}
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
              {(preview.dataset_type === 'image-text' || preview.dataset_type === 'image-only' || sample.image) && (
                <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border bg-muted">
                  {sample._image_exists && sample._image_url ? (
                    <img
                      src={sample._image_url}
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
              )}

              {/* Caption(s) / text */}
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
                {sample.text && !sample.caption && (
                  <p className="text-sm text-card-foreground">{String(sample.text)}</p>
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
                {/* For tabular: show all keys */}
                {!sample.caption && !sample.text && !sample.image && (
                  <div className="space-y-0.5">
                    {Object.entries(sample)
                      .filter(([k]) => !k.startsWith('_'))
                      .map(([k, v]) => (
                        <p key={k} className="text-xs text-muted-foreground">
                          <span className="font-medium">{k}:</span> {String(v)}
                        </p>
                      ))}
                  </div>
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
// Register dataset modal
// ---------------------------------------------------------------------------

const DATASET_TYPES: { value: DatasetType; label: string }[] = [
  { value: 'image-text', label: 'Image + Text' },
  { value: 'text-only', label: 'Text Only' },
  { value: 'image-only', label: 'Image Only' },
  { value: 'tabular', label: 'Tabular' },
  { value: 'custom', label: 'Custom' },
]

const DATASET_FORMATS: { value: DatasetFormat; label: string }[] = [
  { value: 'jsonl', label: 'JSONL' },
  { value: 'csv', label: 'CSV' },
  { value: 'parquet', label: 'Parquet' },
  { value: 'huggingface', label: 'HuggingFace' },
  { value: 'directory', label: 'Directory' },
]

const SPLIT_METHODS: { value: SplitMethod; label: string; desc: string }[] = [
  { value: 'none', label: 'None', desc: 'No split configuration' },
  { value: 'ratio', label: 'Ratio', desc: 'Auto-split by percentage (80/10/10)' },
  { value: 'field', label: 'Field', desc: 'Use a JSON field (e.g. "split")' },
  { value: 'file', label: 'File', desc: 'Separate files per split' },
  { value: 'custom', label: 'Custom', desc: 'Custom filter expressions' },
]

function RegisterModal({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: () => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [dataRoot, setDataRoot] = useState('')
  const [jsonlPath, setJsonlPath] = useState('')
  const [rawPath, setRawPath] = useState('')
  const [dsType, setDsType] = useState<DatasetType>('image-text')
  const [dsFormat, setDsFormat] = useState<DatasetFormat>('jsonl')
  const [rawFormat, setRawFormat] = useState('custom')
  const [splitMethod, setSplitMethod] = useState<SplitMethod>('none')
  const [splitField, setSplitField] = useState('split')
  const [splitRatios, setSplitRatios] = useState('0.8,0.1,0.1')
  const [splitNames, setSplitNames] = useState('train,val,test')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [detecting, setDetecting] = useState(false)
  const [detectResult, setDetectResult] = useState<DetectResult | null>(null)

  const handleDetect = async (path: string) => {
    if (!path.trim()) return
    setDetecting(true)
    try {
      const result = await detectDataset(path)
      setDetectResult(result)
      if (result.format) setDsFormat(result.format as DatasetFormat)
      if (result.type) setDsType(result.type as DatasetType)
      if (result.raw_format) setRawFormat(result.raw_format)
    } catch {
      // ignore detection errors
    } finally {
      setDetecting(false)
    }
  }

  const buildSplitsConfig = (): Record<string, unknown> => {
    if (splitMethod === 'ratio') {
      const names = splitNames.split(',').map((s) => s.trim())
      const ratios = splitRatios.split(',').map((s) => parseFloat(s.trim()))
      const obj: Record<string, number> = {}
      names.forEach((n, i) => {
        obj[n] = ratios[i] ?? 0
      })
      return { ratios: obj }
    }
    if (splitMethod === 'field') {
      return { field: splitField }
    }
    return {}
  }

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload: CreateDatasetPayload = {
        name: name.trim(),
        description: description.trim(),
        dataset_type: dsType,
        dataset_format: dsFormat,
        data_root: dataRoot.trim(),
        jsonl_path: jsonlPath.trim(),
        raw_path: rawPath.trim(),
        raw_format: rawFormat,
        split_method: splitMethod,
        splits_config: buildSplitsConfig(),
      }
      await createDataset(payload)
      onCreated()
      onClose()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to register dataset'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <h3 className="text-lg font-semibold text-card-foreground">Register Dataset</h3>
          <button onClick={onClose} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          {/* Name + Description */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium">Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My Dataset"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Description</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          {/* Path with auto-detect */}
          <div>
            <label className="mb-1 block text-sm font-medium">
              Data Path (JSONL/JSON/CSV file or directory, relative to DATA_DIR)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={jsonlPath || rawPath}
                onChange={(e) => {
                  const v = e.target.value
                  if (v.endsWith('.jsonl')) {
                    setJsonlPath(v)
                  } else {
                    setRawPath(v)
                    if (!jsonlPath) setJsonlPath(v.replace(/\.[^.]+$/, '.jsonl'))
                  }
                }}
                placeholder="path/to/data.jsonl"
                className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <button
                onClick={() => handleDetect(jsonlPath || rawPath)}
                disabled={detecting}
                className="inline-flex items-center gap-1.5 rounded-md border border-input px-3 py-2 text-sm font-medium hover:bg-accent disabled:opacity-50"
              >
                <Search className="h-3.5 w-3.5" />
                {detecting ? 'Detecting...' : 'Detect'}
              </button>
            </div>
            {detectResult && (
              <div className="mt-2 rounded-md bg-muted/50 px-3 py-2 text-xs">
                {detectResult.exists ? (
                  <>
                    <span className="text-green-600">Found</span>
                    {detectResult.type && <> | Type: <strong>{detectResult.type}</strong></>}
                    {detectResult.format && <> | Format: <strong>{detectResult.format}</strong></>}
                    {detectResult.entry_count != null && <> | Entries: <strong>{detectResult.entry_count.toLocaleString()}</strong></>}
                  </>
                ) : (
                  <span className="text-red-500">{detectResult.error || 'Path not found'}</span>
                )}
              </div>
            )}
          </div>

          {/* Data root */}
          <div>
            <label className="mb-1 block text-sm font-medium">Data Root (image directory)</label>
            <input
              type="text"
              value={dataRoot}
              onChange={(e) => setDataRoot(e.target.value)}
              placeholder="path/to/images"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {/* Type + Format */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium">Type</label>
              <select
                value={dsType}
                onChange={(e) => setDsType(e.target.value as DatasetType)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {DATASET_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Format</label>
              <select
                value={dsFormat}
                onChange={(e) => setDsFormat(e.target.value as DatasetFormat)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {DATASET_FORMATS.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Split configuration */}
          <div className="rounded-md border border-border p-4">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Settings2 className="h-4 w-4" />
              Split Configuration
            </h4>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Method</label>
                <select
                  value={splitMethod}
                  onChange={(e) => setSplitMethod(e.target.value as SplitMethod)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {SPLIT_METHODS.map((m) => (
                    <option key={m.value} value={m.value}>{m.label} - {m.desc}</option>
                  ))}
                </select>
              </div>

              {splitMethod === 'ratio' && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs text-muted-foreground">Split Names</label>
                    <input
                      type="text"
                      value={splitNames}
                      onChange={(e) => setSplitNames(e.target.value)}
                      placeholder="train,val,test"
                      className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-muted-foreground">Ratios</label>
                    <input
                      type="text"
                      value={splitRatios}
                      onChange={(e) => setSplitRatios(e.target.value)}
                      placeholder="0.8,0.1,0.1"
                      className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                    />
                  </div>
                </div>
              )}

              {splitMethod === 'field' && (
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">Field Name</label>
                  <input
                    type="text"
                    value={splitField}
                    onChange={(e) => setSplitField(e.target.value)}
                    placeholder="split"
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                  />
                </div>
              )}
            </div>
          </div>

          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
          )}

          <div className="flex justify-end gap-3">
            <button
              onClick={onClose}
              className="rounded-md border border-input px-4 py-2 text-sm font-medium hover:bg-accent"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={saving || !name.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              {saving ? 'Registering...' : 'Register'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Split info display
// ---------------------------------------------------------------------------

function SplitInfo({ dataset }: { dataset: Dataset }) {
  if (dataset.split_method === 'none') return null
  const config = dataset.splits_config || {}

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
      <Settings2 className="h-3 w-3" />
      <span className="font-medium">{dataset.split_method}:</span>
      {dataset.split_method === 'field' && config.field != null && (
        <span className="rounded bg-muted px-1.5 py-0.5">field=&quot;{String(config.field)}&quot;</span>
      )}
      {dataset.split_method === 'ratio' && config.ratios != null && (
        <>
          {Object.entries(config.ratios as Record<string, number>).map(([name, ratio]) => (
            <span key={name} className="rounded bg-muted px-1.5 py-0.5">
              {name}: {(Number(ratio) * 100).toFixed(0)}%
            </span>
          ))}
        </>
      )}
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
  onDelete,
}: {
  dataset: Dataset
  onPreview: (id: number) => void
  onPrepare: (id: number) => void
  onDelete: (id: number) => void
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
            {dataset.is_seed && (
              <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                SEED
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{dataset.description}</p>
        </div>
        <StatusBadge status={dataset.status} />
      </div>

      {/* Stats row */}
      <div className="mb-3 grid grid-cols-4 gap-2">
        <div className="rounded-md bg-muted/50 px-2.5 py-1.5">
          <p className="text-[10px] text-muted-foreground">Entries</p>
          <p className="text-sm font-medium text-card-foreground">
            {dataset.entry_count != null ? dataset.entry_count.toLocaleString() : '-'}
          </p>
        </div>
        <div className="rounded-md bg-muted/50 px-2.5 py-1.5">
          <p className="text-[10px] text-muted-foreground">Size</p>
          <p className="text-sm font-medium text-card-foreground">
            {formatBytes(dataset.size_bytes)}
          </p>
        </div>
        <div className="rounded-md bg-muted/50 px-2.5 py-1.5">
          <p className="text-[10px] text-muted-foreground">Type</p>
          <p className="text-sm font-medium text-card-foreground">
            {dataset.dataset_type}
          </p>
        </div>
        <div className="rounded-md bg-muted/50 px-2.5 py-1.5">
          <p className="text-[10px] text-muted-foreground">Format</p>
          <p className="text-sm font-medium text-card-foreground">
            {dataset.dataset_format}
          </p>
        </div>
      </div>

      {/* Progress bar for preparing */}
      {dataset.status === 'preparing' && dataset.prepare_progress != null && (
        <div className="mb-3">
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
      <div className="mb-3 space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <HardDrive className="h-3 w-3" />
          <span className="truncate">
            {dataset.data_root || '-'} / {dataset.jsonl_path || '-'}
          </span>
        </div>
      </div>

      {/* Split info */}
      <SplitInfo dataset={dataset} />

      {/* Actions */}
      <div className="mt-3 flex items-center gap-2">
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
        {!dataset.is_seed && (
          <button
            onClick={() => onDelete(dataset.id)}
            className="ml-auto inline-flex items-center gap-1 rounded-md border border-input px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:border-destructive hover:text-destructive"
          >
            <Trash2 className="h-3 w-3" />
          </button>
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
  const [showRegister, setShowRegister] = useState(false)

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
      fetchDatasets()
    } catch {
      setError('Failed to start prepare job')
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Remove this dataset registration? (Files will not be deleted)')) return
    try {
      await deleteDataset(id)
      fetchDatasets()
    } catch {
      setError('Failed to delete dataset')
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
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
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
        <button
          onClick={() => setShowRegister(true)}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Register Dataset
        </button>
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
            onDelete={handleDelete}
          />
        ))}
      </div>

      {/* Empty state */}
      {datasets.length === 0 && (
        <div className="py-20 text-center text-muted-foreground">
          <Database className="mx-auto mb-3 h-10 w-10" />
          <p>No datasets registered</p>
          <button
            onClick={() => setShowRegister(true)}
            className="mt-3 inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
          >
            <Plus className="h-4 w-4" />
            Register your first dataset
          </button>
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

      {/* Register modal */}
      {showRegister && (
        <RegisterModal
          onClose={() => setShowRegister(false)}
          onCreated={fetchDatasets}
        />
      )}
    </div>
  )
}
