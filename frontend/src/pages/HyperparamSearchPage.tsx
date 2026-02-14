import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Plus,
  Search,
  Square,
  Trophy,
  XCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ConfigSchema, FieldDef, SchemaDefinition } from '@/types/schema'
import * as schemasApi from '@/api/schemas'
import * as studiesApi from '@/api/studies'
import type {
  CreateStudyRequest,
  ParamImportance,
  SearchSpaceParam,
  StudyResponse,
  TrialResult,
} from '@/api/studies'

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Toggle between Fixed and Search for a single parameter */
function ParamSearchToggle({
  field,
  isSearch,
  searchSpec,
  fixedValue,
  onToggle,
  onSpecChange,
  onFixedChange,
}: {
  field: FieldDef
  isSearch: boolean
  searchSpec: SearchSpaceParam
  fixedValue: unknown
  onToggle: () => void
  onSpecChange: (spec: SearchSpaceParam) => void
  onFixedChange: (value: unknown) => void
}) {
  const isNumeric = field.type === 'number' || field.type === 'slider'
  const isSelect = field.type === 'select'

  return (
    <div className="rounded-md border border-border bg-card p-3">
      <div className="flex items-center justify-between gap-3">
        <label className="text-sm font-medium text-card-foreground">{field.label || field.key}</label>
        <button
          type="button"
          onClick={onToggle}
          className={cn(
            'rounded-full px-3 py-1 text-xs font-medium transition-colors',
            isSearch
              ? 'bg-primary text-primary-foreground'
              : 'bg-secondary text-secondary-foreground',
          )}
        >
          {isSearch ? 'Search' : 'Fixed'}
        </button>
      </div>

      {isSearch ? (
        <div className="mt-2 space-y-2">
          {isNumeric && (
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-muted-foreground">Min</label>
                <input
                  type="number"
                  value={searchSpec.low ?? ''}
                  onChange={(e) => onSpecChange({ ...searchSpec, low: parseFloat(e.target.value) || 0 })}
                  step={field.step ?? 'any'}
                  className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Max</label>
                <input
                  type="number"
                  value={searchSpec.high ?? ''}
                  onChange={(e) => onSpecChange({ ...searchSpec, high: parseFloat(e.target.value) || 0 })}
                  step={field.step ?? 'any'}
                  className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
                />
              </div>
              <label className="col-span-2 flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={searchSpec.log ?? false}
                  onChange={(e) => onSpecChange({ ...searchSpec, log: e.target.checked })}
                />
                Log scale
              </label>
            </div>
          )}
          {isSelect && field.options && (
            <div className="flex flex-wrap gap-1">
              {field.options.map((opt) => {
                const val = typeof opt === 'string' ? opt : opt.value
                const label = typeof opt === 'string' ? opt : opt.label
                const selected = (searchSpec.choices || []).includes(val)
                return (
                  <button
                    key={val}
                    type="button"
                    onClick={() => {
                      const choices = searchSpec.choices || []
                      const next = selected
                        ? choices.filter((c) => c !== val)
                        : [...choices, val]
                      onSpecChange({ ...searchSpec, type: 'categorical', choices: next })
                    }}
                    className={cn(
                      'rounded-md px-2 py-1 text-xs transition-colors',
                      selected
                        ? 'bg-primary text-primary-foreground'
                        : 'border border-input bg-background hover:bg-accent',
                    )}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        <div className="mt-2">
          {isNumeric && (
            <input
              type="number"
              value={fixedValue as number ?? field.default_value ?? ''}
              onChange={(e) => onFixedChange(parseFloat(e.target.value))}
              step={field.step ?? 'any'}
              className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
            />
          )}
          {isSelect && field.options && (
            <select
              value={String(fixedValue ?? field.default_value ?? '')}
              onChange={(e) => onFixedChange(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
            >
              {field.options.map((opt) => {
                const val = typeof opt === 'string' ? opt : opt.value
                const label = typeof opt === 'string' ? opt : opt.label
                return <option key={val} value={val}>{label}</option>
              })}
            </select>
          )}
          {!isNumeric && !isSelect && (
            <input
              type="text"
              value={String(fixedValue ?? field.default_value ?? '')}
              onChange={(e) => onFixedChange(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
            />
          )}
        </div>
      )}
    </div>
  )
}

/** Objective value chart — simple SVG line chart */
function TrialChart({ trials, direction }: { trials: TrialResult[]; direction: string }) {
  const completed = trials.filter((t) => t.status === 'completed' && t.objective_value != null)
  if (completed.length === 0) {
    return <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">No completed trials yet</div>
  }

  const values = completed.map((t) => t.objective_value!)
  const minVal = Math.min(...values)
  const maxVal = Math.max(...values)
  const range = maxVal - minVal || 1

  const W = 600
  const H = 180
  const PAD = 30

  // Best-so-far line
  const bestSoFar: number[] = []
  let currentBest = direction === 'maximize' ? -Infinity : Infinity
  for (const v of values) {
    if (direction === 'maximize' ? v > currentBest : v < currentBest) currentBest = v
    bestSoFar.push(currentBest)
  }

  const xScale = (i: number) => PAD + (i / Math.max(completed.length - 1, 1)) * (W - 2 * PAD)
  const yScale = (v: number) => H - PAD - ((v - minVal) / range) * (H - 2 * PAD)

  const pointsLine = completed.map((_, i) => `${xScale(i)},${yScale(values[i])}`).join(' ')
  const bestLine = bestSoFar.map((v, i) => `${xScale(i)},${yScale(v)}`).join(' ')

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((f) => {
        const y = H - PAD - f * (H - 2 * PAD)
        const val = minVal + f * range
        return (
          <g key={f}>
            <line x1={PAD} y1={y} x2={W - PAD} y2={y} stroke="currentColor" strokeOpacity={0.1} />
            <text x={PAD - 4} y={y + 3} textAnchor="end" className="fill-muted-foreground text-[8px]">
              {val.toFixed(4)}
            </text>
          </g>
        )
      })}

      {/* Trial values */}
      <polyline points={pointsLine} fill="none" stroke="hsl(var(--muted-foreground))" strokeWidth={1} strokeOpacity={0.4} />
      {completed.map((t, i) => (
        <circle
          key={t.trial_number}
          cx={xScale(i)}
          cy={yScale(values[i])}
          r={3}
          className="fill-primary"
          opacity={0.7}
        >
          <title>Trial #{t.trial_number}: {values[i].toFixed(6)}</title>
        </circle>
      ))}

      {/* Best-so-far line */}
      <polyline points={bestLine} fill="none" stroke="hsl(var(--primary))" strokeWidth={2} />

      {/* X-axis label */}
      <text x={W / 2} y={H - 4} textAnchor="middle" className="fill-muted-foreground text-[9px]">
        Trial #
      </text>
    </svg>
  )
}

/** Param importance bar chart */
function ImportanceChart({ importance }: { importance: ParamImportance }) {
  const entries = Object.entries(importance.importances).sort(([, a], [, b]) => b - a)
  if (entries.length === 0) return null

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-card-foreground">Parameter Importance</h3>
      {entries.map(([key, val]) => (
        <div key={key} className="flex items-center gap-2">
          <span className="w-32 truncate text-xs text-muted-foreground">{key}</span>
          <div className="h-4 flex-1 rounded-full bg-secondary">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${Math.max(val * 100, 2)}%` }}
            />
          </div>
          <span className="w-12 text-right text-xs text-muted-foreground">{(val * 100).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  )
}

/** Trial results table */
function TrialTable({
  trials,
  bestTrialNumber,
  searchSpace,
}: {
  trials: TrialResult[]
  bestTrialNumber: number | null
  searchSpace: Record<string, SearchSpaceParam>
}) {
  const paramKeys = Object.keys(searchSpace)

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="px-2 py-2 text-left font-medium text-muted-foreground">#</th>
            <th className="px-2 py-2 text-left font-medium text-muted-foreground">Status</th>
            <th className="px-2 py-2 text-right font-medium text-muted-foreground">Objective</th>
            {paramKeys.map((k) => (
              <th key={k} className="px-2 py-2 text-right font-medium text-muted-foreground">{k}</th>
            ))}
            <th className="px-2 py-2 text-right font-medium text-muted-foreground">Duration</th>
          </tr>
        </thead>
        <tbody>
          {trials.map((trial) => {
            const isBest = trial.trial_number === bestTrialNumber
            return (
              <tr
                key={trial.id}
                className={cn(
                  'border-b border-border/50 transition-colors hover:bg-accent/50',
                  isBest && 'bg-primary/5',
                )}
              >
                <td className="px-2 py-1.5">
                  <span className="flex items-center gap-1">
                    {isBest && <Trophy className="h-3.5 w-3.5 text-yellow-500" />}
                    {trial.trial_number}
                  </span>
                </td>
                <td className="px-2 py-1.5">
                  {trial.status === 'completed' && <CheckCircle2 className="h-4 w-4 text-green-500" />}
                  {trial.status === 'running' && <Loader2 className="h-4 w-4 animate-spin text-blue-500" />}
                  {trial.status === 'failed' && <XCircle className="h-4 w-4 text-destructive" />}
                  {trial.status === 'pruned' && <Square className="h-4 w-4 text-muted-foreground" />}
                </td>
                <td className="px-2 py-1.5 text-right font-mono text-xs">
                  {trial.objective_value?.toFixed(6) ?? '-'}
                </td>
                {paramKeys.map((k) => {
                  const v = trial.params_json[k]
                  const display = typeof v === 'number' ? v.toFixed(6) : String(v ?? '-')
                  return (
                    <td key={k} className="px-2 py-1.5 text-right font-mono text-xs">
                      {display}
                    </td>
                  )
                })}
                <td className="px-2 py-1.5 text-right text-xs text-muted-foreground">
                  {trial.duration_seconds ? `${trial.duration_seconds.toFixed(1)}s` : '-'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function HyperparamSearchPage() {
  const navigate = useNavigate()
  const { studyId } = useParams<{ studyId: string }>()
  const isViewMode = !!studyId

  // ── Schema + Form state ────────────────────────────────────────
  const [schemas, setSchemas] = useState<ConfigSchema[]>([])
  const [schemaId, setSchemaId] = useState<number | null>(null)
  const [studyName, setStudyName] = useState('')
  const [searchModes, setSearchModes] = useState<Record<string, boolean>>({})
  const [searchSpecs, setSearchSpecs] = useState<Record<string, SearchSpaceParam>>({})
  const [fixedValues, setFixedValues] = useState<Record<string, unknown>>({})

  // ── Optuna settings ─────────────────────────────────────────────
  const [nTrials, setNTrials] = useState(20)
  const [searchEpochs, setSearchEpochs] = useState(5)
  const [subsetRatio, setSubsetRatio] = useState(0.1)
  const [pruner, setPruner] = useState('median')
  const [objectiveMetric, setObjectiveMetric] = useState('val/map_i2t')
  const [direction, setDirection] = useState('maximize')

  // ── Study state (view mode) ─────────────────────────────────────
  const [study, setStudy] = useState<StudyResponse | null>(null)
  const [importance, setImportance] = useState<ParamImportance | null>(null)
  const [polling, setPolling] = useState(false)

  // ── UI state ────────────────────────────────────────────────────
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Active schema fields
  const activeSchema: SchemaDefinition | null = useMemo(() => {
    if (!schemaId) return null
    const found = schemas.find((s) => s.id === schemaId)
    if (!found) return null
    const raw = found.fields_schema
    if (raw && 'fields' in raw && Array.isArray(raw.fields)) {
      return raw as SchemaDefinition
    }
    return null
  }, [schemaId, schemas])

  const fields: FieldDef[] = useMemo(() => {
    if (!activeSchema) return []
    return activeSchema.fields || []
  }, [activeSchema])

  // ── Load schemas ─────────────────────────────────────────────────
  useEffect(() => {
    schemasApi.getSchemas().then((res) => setSchemas(res.schemas)).catch(() => {})
  }, [])

  // ── Load study if in view mode ──────────────────────────────────
  useEffect(() => {
    if (!studyId) return
    const load = async () => {
      try {
        const s = await studiesApi.getStudy(Number(studyId))
        setStudy(s)
        setStudyName(s.name)
        setSchemaId(s.config_schema_id)

        // Set search space from study
        const searchKeys = Object.keys(s.search_space_json)
        const modes: Record<string, boolean> = {}
        for (const k of searchKeys) modes[k] = true
        setSearchModes(modes)
        setSearchSpecs(s.search_space_json as Record<string, SearchSpaceParam>)
        setFixedValues(s.base_config_json)

        // If running, start polling
        if (s.status === 'running') {
          setPolling(true)
        }

        // If completed, fetch importance
        if (s.status === 'completed') {
          const imp = await studiesApi.getParamImportance(Number(studyId))
          setImportance(imp)
        }
      } catch {
        setError('Failed to load study')
      }
    }
    load()
  }, [studyId])

  // ── Polling for running study ───────────────────────────────────
  useEffect(() => {
    if (!polling || !studyId) return

    const interval = setInterval(async () => {
      try {
        const s = await studiesApi.getStudy(Number(studyId))
        setStudy(s)

        if (s.status !== 'running') {
          setPolling(false)
          // Fetch importance on completion
          if (s.status === 'completed') {
            const imp = await studiesApi.getParamImportance(Number(studyId))
            setImportance(imp)
          }
        }
      } catch {
        // ignore polling errors
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [polling, studyId])

  // ── Schema selection ────────────────────────────────────────────
  const handleSchemaSelect = useCallback(
    (id: number | null) => {
      setSchemaId(id)
      if (!id) return
      const found = schemas.find((s) => s.id === id)
      if (!found) return
      const raw = found.fields_schema
      if (raw && 'fields' in raw && Array.isArray(raw.fields)) {
        const defaults: Record<string, unknown> = {}
        const modes: Record<string, boolean> = {}
        const specs: Record<string, SearchSpaceParam> = {}
        for (const f of raw.fields as FieldDef[]) {
          if (f.default_value !== undefined) defaults[f.key] = f.default_value
          modes[f.key] = false
          // Initialize search specs from field metadata
          if (f.type === 'number' || f.type === 'slider') {
            specs[f.key] = {
              type: 'float',
              low: f.min ?? 0,
              high: f.max ?? 1,
              log: false,
            }
          } else if (f.type === 'select' && f.options) {
            specs[f.key] = {
              type: 'categorical',
              choices: f.options.map((o) => (typeof o === 'string' ? o : o.value)),
            }
          }
        }
        setFixedValues((prev) => ({ ...defaults, ...prev }))
        setSearchModes(modes)
        setSearchSpecs(specs)
      }
    },
    [schemas],
  )

  // ── Handlers ────────────────────────────────────────────────────
  const toggleSearch = (key: string) => {
    setSearchModes((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleStartSearch = async () => {
    if (!studyName.trim()) {
      setError('Study name is required')
      return
    }

    // Build search space and base config
    const searchSpace: Record<string, SearchSpaceParam> = {}
    const baseConfig: Record<string, unknown> = {}

    for (const field of fields) {
      if (searchModes[field.key]) {
        searchSpace[field.key] = searchSpecs[field.key]
      } else {
        baseConfig[field.key] = fixedValues[field.key] ?? field.default_value
      }
    }

    if (Object.keys(searchSpace).length === 0) {
      setError('Select at least one parameter for search')
      return
    }

    setError('')
    setSaving(true)

    try {
      const req: CreateStudyRequest = {
        name: studyName,
        config_schema_id: schemaId,
        base_config_json: baseConfig,
        search_space_json: searchSpace,
        n_trials: nTrials,
        search_epochs: searchEpochs,
        subset_ratio: subsetRatio,
        pruner,
        objective_metric: objectiveMetric,
        direction,
      }

      const created = await studiesApi.createStudy(req)
      const started = await studiesApi.startStudy(created.id)
      navigate(`/hyperparam/${started.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start search')
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = async () => {
    if (!study) return
    try {
      await studiesApi.cancelStudy(study.id)
      setPolling(false)
      const s = await studiesApi.getStudy(study.id)
      setStudy(s)
    } catch {
      setError('Failed to cancel study')
    }
  }

  const handleCreateExperiment = async () => {
    if (!study) return
    setSaving(true)
    try {
      const result = await studiesApi.createExperimentFromTrial(study.id, {
        tags: ['optuna-best'],
      })
      navigate(`/experiments/${result.experiment_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create experiment')
    } finally {
      setSaving(false)
    }
  }

  // ── Computed ─────────────────────────────────────────────────────
  const completedTrials = study?.trials.filter((t) => t.status === 'completed').length ?? 0
  const totalTrials = study?.n_trials ?? nTrials
  const progressPct = study ? Math.round((completedTrials / totalTrials) * 100) : 0

  // ── Render ──────────────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-5xl">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <button
          onClick={() => navigate('/hyperparam')}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-2xl font-bold text-foreground">
          {isViewMode ? study?.name || 'Loading...' : 'New Hyperparameter Search'}
        </h1>
        {study && (
          <span
            className={cn(
              'rounded-full px-2.5 py-0.5 text-xs font-medium',
              study.status === 'running' && 'bg-blue-500/10 text-blue-500',
              study.status === 'completed' && 'bg-green-500/10 text-green-500',
              study.status === 'failed' && 'bg-destructive/10 text-destructive',
              study.status === 'pending' && 'bg-yellow-500/10 text-yellow-600',
              study.status === 'cancelled' && 'bg-muted text-muted-foreground',
            )}
          >
            {study.status}
          </span>
        )}
      </div>

      {/* ── VIEW MODE: Study monitoring ────────────────────────── */}
      {isViewMode && study && (
        <div className="space-y-6">
          {/* Progress bar */}
          <section className="rounded-lg border border-border bg-card p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-card-foreground">
                Trial Progress: {completedTrials} / {totalTrials}
              </span>
              <span className="text-sm text-muted-foreground">{progressPct}%</span>
            </div>
            <div className="h-2 w-full rounded-full bg-secondary">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            {study.status === 'running' && (
              <div className="mt-3 flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span className="text-sm text-muted-foreground">Search in progress...</span>
                <button
                  onClick={handleCancel}
                  className="ml-auto rounded-md border border-destructive/30 px-3 py-1 text-xs font-medium text-destructive hover:bg-destructive/10"
                >
                  Cancel
                </button>
              </div>
            )}
          </section>

          {/* Best trial highlight */}
          {study.best_value != null && study.best_trial_number != null && (
            <section className="rounded-lg border border-primary/30 bg-primary/5 p-4">
              <div className="flex items-center gap-2">
                <Trophy className="h-5 w-5 text-yellow-500" />
                <h2 className="font-semibold text-card-foreground">Best Trial #{study.best_trial_number}</h2>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {study.objective_metric}: <span className="font-mono font-medium text-foreground">{study.best_value.toFixed(6)}</span>
                {' '}({study.direction})
              </p>
              {study.trials.find((t) => t.trial_number === study.best_trial_number) && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(
                    study.trials.find((t) => t.trial_number === study.best_trial_number)!.params_json,
                  ).map(([k, v]) => (
                    <span key={k} className="rounded-md bg-card px-2 py-1 text-xs">
                      <span className="text-muted-foreground">{k}:</span>{' '}
                      <span className="font-mono">{typeof v === 'number' ? v.toFixed(6) : String(v)}</span>
                    </span>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Objective value chart */}
          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-sm font-semibold text-card-foreground">
              Objective Value ({study.objective_metric})
            </h2>
            <TrialChart trials={study.trials} direction={study.direction} />
          </section>

          {/* Param importance (after completion) */}
          {importance && Object.keys(importance.importances).length > 0 && (
            <section className="rounded-lg border border-border bg-card p-4">
              <ImportanceChart importance={importance} />
            </section>
          )}

          {/* Trial table */}
          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-sm font-semibold text-card-foreground">Trial Results</h2>
            <TrialTable
              trials={study.trials}
              bestTrialNumber={study.best_trial_number}
              searchSpace={study.search_space_json as Record<string, SearchSpaceParam>}
            />
          </section>

          {/* Create experiment button (after completion) */}
          {study.status === 'completed' && study.best_value != null && (
            <div className="flex justify-end border-t border-border pt-4">
              <button
                onClick={handleCreateExperiment}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                {saving ? 'Creating...' : 'Create Experiment from Best Trial'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── CREATE MODE: Search setup form ─────────────────────── */}
      {!isViewMode && (
        <div className="space-y-6">
          {/* Basic info */}
          <section className="rounded-lg border border-border bg-card p-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-card-foreground">
                  Study Name <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  value={studyName}
                  onChange={(e) => setStudyName(e.target.value)}
                  placeholder="optuna-search-001"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-card-foreground">Template</label>
                <select
                  value={schemaId ?? ''}
                  onChange={(e) => handleSchemaSelect(e.target.value ? Number(e.target.value) : null)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">Select template...</option>
                  {schemas.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          {/* Search space: parameter toggles */}
          {fields.length > 0 && (
            <section>
              <h2 className="mb-3 text-lg font-semibold text-foreground">
                Parameters — Fixed / Search
              </h2>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {fields.map((field) => (
                  <ParamSearchToggle
                    key={field.key}
                    field={field}
                    isSearch={searchModes[field.key] ?? false}
                    searchSpec={searchSpecs[field.key] ?? { type: 'float', low: 0, high: 1 }}
                    fixedValue={fixedValues[field.key]}
                    onToggle={() => toggleSearch(field.key)}
                    onSpecChange={(spec) => setSearchSpecs((prev) => ({ ...prev, [field.key]: spec }))}
                    onFixedChange={(val) => setFixedValues((prev) => ({ ...prev, [field.key]: val }))}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Optuna settings */}
          <section className="rounded-lg border border-border bg-card p-5">
            <h2 className="mb-3 text-sm font-semibold text-card-foreground">Search Settings</h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">Trials</label>
                <input
                  type="number"
                  value={nTrials}
                  onChange={(e) => setNTrials(parseInt(e.target.value) || 20)}
                  min={1}
                  max={500}
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">Epochs per Trial</label>
                <input
                  type="number"
                  value={searchEpochs}
                  onChange={(e) => setSearchEpochs(parseInt(e.target.value) || 5)}
                  min={1}
                  max={100}
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">Subset Ratio</label>
                <input
                  type="number"
                  value={subsetRatio}
                  onChange={(e) => setSubsetRatio(parseFloat(e.target.value) || 0.1)}
                  min={0.01}
                  max={1.0}
                  step={0.01}
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">Pruner</label>
                <select
                  value={pruner}
                  onChange={(e) => setPruner(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                >
                  <option value="median">Median</option>
                  <option value="hyperband">Hyperband</option>
                  <option value="none">None</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">Objective Metric</label>
                <input
                  type="text"
                  value={objectiveMetric}
                  onChange={(e) => setObjectiveMetric(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">Direction</label>
                <select
                  value={direction}
                  onChange={(e) => setDirection(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                >
                  <option value="maximize">Maximize</option>
                  <option value="minimize">Minimize</option>
                </select>
              </div>
            </div>
          </section>

          {/* Error */}
          {error && (
            <p className="rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</p>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 border-t border-border pt-4">
            <button
              onClick={() => navigate('/')}
              className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-accent"
            >
              Cancel
            </button>
            <button
              onClick={handleStartSearch}
              disabled={saving || !studyName.trim()}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              Start Search
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
