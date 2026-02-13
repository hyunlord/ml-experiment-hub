import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Play, Save, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { configToYaml, yamlToConfig } from '@/lib/config'
import { DynamicForm } from '@/components/DynamicForm'
import type { ConfigSchema, FieldDef, SchemaDefinition } from '@/types/schema'
import * as schemasApi from '@/api/schemas'
import client from '@/api/client'

// ---------------------------------------------------------------------------
// Types matching the new backend API
// ---------------------------------------------------------------------------

interface ExperimentCreatePayload {
  name: string
  description?: string
  config: Record<string, unknown>
  schema_id?: number | null
  tags: string[]
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ExperimentCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // ── Form state ────────────────────────────────────────────────────
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')
  const [schemaId, setSchemaId] = useState<number | null>(null)
  const [config, setConfig] = useState<Record<string, unknown>>({})

  // ── YAML preview state ────────────────────────────────────────────
  const [yamlText, setYamlText] = useState('')
  const [yamlEditing, setYamlEditing] = useState(false)
  const [yamlError, setYamlError] = useState('')

  // ── Schema catalog ────────────────────────────────────────────────
  const [schemas, setSchemas] = useState<ConfigSchema[]>([])
  const [schemasLoading, setSchemasLoading] = useState(true)

  // ── UI state ──────────────────────────────────────────────────────
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // ── Derived: active schema definition ─────────────────────────────
  const activeSchema: SchemaDefinition | null = useMemo(() => {
    if (!schemaId) return null
    const found = schemas.find((s) => s.id === schemaId)
    if (!found) return null

    const raw = found.fields_schema
    // Normalize: backend stores either {fields: [...]} or raw dict
    if (raw && 'fields' in raw && Array.isArray(raw.fields)) {
      return raw as SchemaDefinition
    }
    return null
  }, [schemaId, schemas])

  // ── Fetch schemas on mount ────────────────────────────────────────
  useEffect(() => {
    schemasApi.getSchemas().then((res) => {
      setSchemas(res.schemas)
      setSchemasLoading(false)
    }).catch(() => setSchemasLoading(false))
  }, [])

  // ── Handle clone: load experiment from query param ────────────────
  useEffect(() => {
    const cloneId = searchParams.get('clone')
    if (!cloneId) return

    client.get(`/experiments/${cloneId}`).then((res) => {
      const exp = res.data
      setName(exp.name ? `${exp.name} (copy)` : '')
      setDescription(exp.description || '')
      setTags(exp.tags || [])
      setSchemaId(exp.schema_id || null)
      setConfig(exp.config || {})
    }).catch(() => {
      setError('Failed to load experiment for cloning')
    })
  }, [searchParams])

  // ── Sync config → YAML (when not manually editing YAML) ──────────
  useEffect(() => {
    if (!yamlEditing) {
      setYamlText(configToYaml(config))
      setYamlError('')
    }
  }, [config, yamlEditing])

  // ── Config change handler ─────────────────────────────────────────
  const handleConfigChange = useCallback((key: string, value: unknown) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
    setYamlEditing(false) // reset manual YAML edit flag
  }, [])

  // ── YAML → config sync ───────────────────────────────────────────
  const handleYamlChange = useCallback((text: string) => {
    setYamlText(text)
    setYamlEditing(true)
    try {
      const parsed = yamlToConfig(text)
      setConfig(parsed)
      setYamlError('')
    } catch (e) {
      setYamlError((e as Error).message)
    }
  }, [])

  // ── Schema template selection ─────────────────────────────────────
  const handleSchemaSelect = useCallback(
    (id: number | null) => {
      setSchemaId(id)
      if (!id) return

      const found = schemas.find((s) => s.id === id)
      if (!found) return

      const raw = found.fields_schema
      if (raw && 'fields' in raw && Array.isArray(raw.fields)) {
        // Set defaults from schema fields
        const defaults: Record<string, unknown> = {}
        for (const field of raw.fields as FieldDef[]) {
          if (field.default_value !== undefined) {
            defaults[field.key] = field.default_value
          }
        }
        setConfig((prev) => ({ ...defaults, ...prev }))
      }
    },
    [schemas],
  )

  // ── Add free-form field ───────────────────────────────────────────
  const handleAddField = useCallback((_field: FieldDef) => {
    // Field value is set via onChange in DynamicForm
  }, [])

  // ── Tag management ────────────────────────────────────────────────
  const addTag = () => {
    const trimmed = tagInput.trim()
    if (trimmed && !tags.includes(trimmed)) {
      setTags([...tags, trimmed])
    }
    setTagInput('')
  }

  const removeTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag))
  }

  const handleTagKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTag()
    }
  }

  // ── Save handlers ─────────────────────────────────────────────────
  const buildPayload = (): ExperimentCreatePayload => ({
    name: name.trim(),
    description: description.trim() || undefined,
    config,
    schema_id: schemaId,
    tags,
  })

  const handleSaveDraft = async () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    setError('')
    setSaving(true)
    try {
      const res = await client.post('/experiments', buildPayload())
      navigate(`/experiments/${res.data.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save experiment')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveAndStart = async () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    setError('')
    setSaving(true)
    try {
      const createRes = await client.post('/experiments', buildPayload())
      const expId = createRes.data.id
      // Start training run
      await client.post(`/experiments/${expId}/start`)
      navigate(`/experiments/${expId}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save and start experiment')
    } finally {
      setSaving(false)
    }
  }

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-4xl">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <button
          onClick={() => navigate('/')}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-2xl font-bold text-foreground">Create New Experiment</h1>
      </div>

      <div className="space-y-6">
        {/* ── Basic Info ────────────────────────────────────────── */}
        <section className="rounded-lg border border-border bg-card p-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Name */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-card-foreground">
                Name <span className="text-destructive">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="experiment-name"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {/* Template */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-card-foreground">
                Template
              </label>
              <select
                value={schemaId ?? ''}
                onChange={(e) =>
                  handleSchemaSelect(e.target.value ? Number(e.target.value) : null)
                }
                disabled={schemasLoading}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="">
                  {schemasLoading ? 'Loading schemas...' : 'No template (free-form)'}
                </option>
                {schemas.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Description */}
            <div className="md:col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-card-foreground">
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of this experiment"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {/* Tags */}
            <div className="md:col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-card-foreground">
                Tags
              </label>
              <div className="flex flex-wrap items-center gap-2">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 rounded-md bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="rounded-sm opacity-70 transition-opacity hover:opacity-100"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleTagKeyDown}
                  onBlur={addTag}
                  placeholder="Add tag..."
                  className="min-w-[100px] flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
          </div>
        </section>

        {/* ── Config Form (DynamicForm) ────────────────────────── */}
        <section>
          <h2 className="mb-3 text-lg font-semibold text-foreground">Configuration</h2>
          <DynamicForm
            schema={activeSchema}
            values={config}
            onChange={handleConfigChange}
            onAddField={handleAddField}
            disabled={saving}
          />
        </section>

        {/* ── YAML Preview ─────────────────────────────────────── */}
        <section className="rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold text-card-foreground">
              Config Preview (YAML)
            </h2>
            <span className={cn(
              'text-xs',
              yamlEditing ? 'text-primary' : 'text-muted-foreground',
            )}>
              {yamlEditing ? 'Editing YAML' : 'Auto-synced from form'}
            </span>
          </div>
          <div className="p-4">
            <textarea
              value={yamlText}
              onChange={(e) => handleYamlChange(e.target.value)}
              rows={Math.max(8, yamlText.split('\n').length + 2)}
              spellCheck={false}
              disabled={saving}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            />
            {yamlError && (
              <p className="mt-1 text-xs text-destructive">Parse error: {yamlError}</p>
            )}
          </div>
        </section>

        {/* ── Error ────────────────────────────────────────────── */}
        {error && (
          <p className="rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {/* ── Actions ──────────────────────────────────────────── */}
        <div className="flex items-center justify-end gap-3 border-t border-border pt-4">
          <button
            type="button"
            onClick={() => navigate('/')}
            disabled={saving}
            className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSaveDraft}
            disabled={saving || !name.trim()}
            className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            Save as Draft
          </button>
          <button
            type="button"
            onClick={handleSaveAndStart}
            disabled={saving || !name.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className="h-4 w-4" />
            Save &amp; Start Training
          </button>
        </div>
      </div>
    </div>
  )
}
