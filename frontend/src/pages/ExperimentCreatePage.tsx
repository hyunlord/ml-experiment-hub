import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  ChevronDown,
  ClipboardCopy,
  Code,
  Eye,
  FileText,
  GitCompare,
  Layers,
  Play,
  Plus,
  RotateCcw,
  Save,
  Trash2,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { configToYaml, yamlToConfig } from '@/lib/config'
import { getProjects, parseConfig } from '@/api/projects'
import client from '@/api/client'
import type { Project, ConfigFileInfo, ParsedConfigResponse } from '@/types/project'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ExperimentCreatePayload {
  name: string
  description?: string
  config: Record<string, unknown>
  schema_id?: number | null
  project_id?: number | null
  base_config_path?: string | null
  tags: string[]
}

interface DryRunResult {
  config_yaml: string
  command: string[]
  working_dir: string
  effective_config: Record<string, unknown>
  warnings: string[]
}

type ViewMode = 'form' | 'yaml' | 'diff'

// Group icon mapping
const GROUP_ICONS: Record<string, string> = {
  model: '\u{1F4E6}',
  training: '\u{1F3CB}',
  data: '\u{1F4CA}',
  loss: '\u{2696}',
  optimizer: '\u{26A1}',
  scheduler: '\u{23F0}',
  evaluation: '\u{1F3AF}',
  general: '\u{2699}',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ExperimentCreatePage() {
  const navigate = useNavigate()
  const { id: editId } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const isEditMode = Boolean(editId)

  // ── Project & Config state ──────────────────────────────────────
  const [projects, setProjects] = useState<Project[]>([])
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [selectedConfigPath, setSelectedConfigPath] = useState<string | null>(null)
  const [parsedConfig, setParsedConfig] = useState<ParsedConfigResponse | null>(null)
  const [parseLoading, setParseLoading] = useState(false)

  // ── Form state ──────────────────────────────────────────────────
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')
  const [config, setConfig] = useState<Record<string, unknown>>({})
  const [originalConfig, setOriginalConfig] = useState<Record<string, unknown>>({})

  // ── View mode ───────────────────────────────────────────────────
  const [viewMode, setViewMode] = useState<ViewMode>('form')
  const [yamlText, setYamlText] = useState('')
  const [yamlError, setYamlError] = useState('')
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  // ── Add parameter dialog ────────────────────────────────────────
  const [showAddParam, setShowAddParam] = useState(false)
  const [newParamGroup, setNewParamGroup] = useState('')
  const [newParamKey, setNewParamKey] = useState('')
  const [newParamType, setNewParamType] = useState('string')
  const [newParamValue, setNewParamValue] = useState('')

  // ── UI state ────────────────────────────────────────────────────
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null)
  const [dryRunning, setDryRunning] = useState(false)
  const [draftId, setDraftId] = useState<number | null>(null)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [nameError, setNameError] = useState('')
  const [nameSuggestion, setNameSuggestion] = useState('')
  const [nameCheckTimer, setNameCheckTimer] = useState<ReturnType<typeof setTimeout> | null>(null)

  // ── Derived: selected project ───────────────────────────────────
  const selectedProject = useMemo(
    () => projects.find((p) => p.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  )

  const availableConfigs: ConfigFileInfo[] = useMemo(
    () => selectedProject?.detected_configs ?? [],
    [selectedProject],
  )

  // ── Derived: config groups for Form View ────────────────────────
  const configGroups = useMemo(() => {
    if (!parsedConfig) {
      // Build groups from flat config (free-form / from-scratch mode)
      const entries = Object.entries(config)
      if (entries.length === 0) return []

      // Group by dot-notation prefix
      const groups = new Map<string, Array<{ key: string; fullKey: string; value: unknown }>>()
      for (const [key, value] of entries) {
        const dotIdx = key.indexOf('.')
        const group = dotIdx > 0 ? key.substring(0, dotIdx) : 'general'
        const subKey = dotIdx > 0 ? key.substring(dotIdx + 1) : key
        if (!groups.has(group)) groups.set(group, [])
        groups.get(group)!.push({ key: subKey, fullKey: key, value })
      }
      return Array.from(groups.entries()).map(([name, fields]) => ({ name, fields }))
    }

    // Build from parsed config structure
    return parsedConfig.groups.map((groupName) => {
      const groupFields = parsedConfig.parsed[groupName] || {}
      return {
        name: groupName,
        fields: Object.entries(groupFields).map(([key, meta]) => ({
          key,
          fullKey: `${groupName}.${key}`,
          value: config[`${groupName}.${key}`] ?? meta.value,
          type: meta.type,
          originalValue: meta.value,
        })),
      }
    })
  }, [parsedConfig, config])

  // ── Changed keys tracking ───────────────────────────────────────
  const changedKeys = useMemo(() => {
    const changed = new Set<string>()
    for (const key of Object.keys(config)) {
      if (JSON.stringify(config[key]) !== JSON.stringify(originalConfig[key])) {
        changed.add(key)
      }
    }
    // Keys in original but removed from config
    for (const key of Object.keys(originalConfig)) {
      if (!(key in config)) {
        changed.add(key)
      }
    }
    return changed
  }, [config, originalConfig])

  // ── Fetch projects on mount ─────────────────────────────────────
  useEffect(() => {
    getProjects()
      .then((res) => {
        setProjects(res.projects || [])
        setProjectsLoading(false)
      })
      .catch(() => setProjectsLoading(false))
  }, [])

  // ── Handle query params ─────────────────────────────────────────
  useEffect(() => {
    const projectIdParam = searchParams.get('project_id')
    const configParam = searchParams.get('config')
    const cloneFromParam = searchParams.get('clone_from')

    if (projectIdParam && !projectsLoading) {
      const pid = Number(projectIdParam)
      setSelectedProjectId(pid)
      if (configParam) {
        setSelectedConfigPath(configParam)
      }
    }

    if (cloneFromParam) {
      client
        .get(`/experiments/${cloneFromParam}`)
        .then((res) => {
          const exp = res.data
          setName(exp.name ? `${exp.name}_copy` : '')
          setDescription(exp.description || '')
          setTags(exp.tags || [])
          if (exp.project_id) setSelectedProjectId(exp.project_id)
          const flat = exp.config || {}
          setConfig(flat)
          setOriginalConfig(flat)
        })
        .catch(() => setError('Failed to load experiment for cloning'))
    }
  }, [searchParams, projectsLoading])

  // ── Load experiment for edit mode ──────────────────────────────
  useEffect(() => {
    if (!editId || projectsLoading) return
    client
      .get(`/experiments/${editId}`)
      .then((res) => {
        const exp = res.data
        setName(exp.name || '')
        setDescription(exp.description || '')
        setTags(exp.tags || [])
        if (exp.project_id) setSelectedProjectId(exp.project_id)
        const flat = exp.config || {}
        setConfig(flat)
        setOriginalConfig(flat)
        setDraftId(Number(editId))
      })
      .catch(() => setError('Failed to load experiment'))
  }, [editId, projectsLoading])

  // ── Parse config when selection changes ─────────────────────────
  useEffect(() => {
    if (!selectedProjectId || !selectedConfigPath) {
      return
    }

    setParseLoading(true)
    setError('')
    parseConfig(selectedProjectId, selectedConfigPath)
      .then((result) => {
        setParsedConfig(result)

        // Flatten parsed config to dot-notation for form state
        const flat: Record<string, unknown> = {}
        for (const [group, fields] of Object.entries(result.parsed)) {
          for (const [key, meta] of Object.entries(fields as Record<string, { value: unknown }>)) {
            flat[`${group}.${key}`] = meta.value
          }
        }
        setConfig(flat)
        setOriginalConfig({ ...flat })

        // Auto-generate name if empty
        if (!name) {
          const project = projects.find((p) => p.id === selectedProjectId)
          const configName = selectedConfigPath
            .replace(/^configs\//, '')
            .replace(/\.(yaml|yml|json)$/, '')
          setName(`${project?.name ?? 'exp'}_${configName}_001`)
        }
      })
      .catch((e) => {
        setError(e?.response?.data?.detail || 'Failed to parse config file')
        setParsedConfig(null)
      })
      .finally(() => setParseLoading(false))
  }, [selectedProjectId, selectedConfigPath])

  // ── Sync config → YAML text ─────────────────────────────────────
  useEffect(() => {
    if (viewMode !== 'yaml') {
      setYamlText(configToYaml(config))
      setYamlError('')
    }
  }, [config, viewMode])

  // ── Config change handler ───────────────────────────────────────
  const handleConfigChange = useCallback((key: string, value: unknown) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
  }, [])

  // ── YAML → config apply ─────────────────────────────────────────
  const handleYamlApply = useCallback(() => {
    try {
      const parsed = yamlToConfig(yamlText)
      setConfig(parsed)
      setYamlError('')
      setViewMode('form')
    } catch (e) {
      setYamlError((e as Error).message)
    }
  }, [yamlText])

  // ── Reset single field ──────────────────────────────────────────
  const handleResetField = useCallback(
    (key: string) => {
      if (key in originalConfig) {
        setConfig((prev) => ({ ...prev, [key]: originalConfig[key] }))
      }
    },
    [originalConfig],
  )

  // ── Delete field ────────────────────────────────────────────────
  const handleDeleteField = useCallback((key: string) => {
    setConfig((prev) => {
      const next = { ...prev }
      delete next[key]
      return next
    })
  }, [])

  // ── Copy value ──────────────────────────────────────────────────
  const handleCopyValue = useCallback((key: string, value: unknown) => {
    const text = typeof value === 'object' ? JSON.stringify(value) : String(value)
    navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey(null), 1500)
  }, [])

  // ── Add parameter ──────────────────────────────────────────────
  const handleAddParameter = useCallback(() => {
    if (!newParamKey.trim()) return
    const group = newParamGroup.trim() || 'general'
    const fullKey = `${group}.${newParamKey.trim()}`

    let value: unknown = newParamValue
    if (newParamType === 'integer') value = parseInt(newParamValue) || 0
    else if (newParamType === 'float') value = parseFloat(newParamValue) || 0.0
    else if (newParamType === 'boolean') value = newParamValue === 'true'
    else if (newParamType === 'array') {
      try {
        value = JSON.parse(newParamValue)
      } catch {
        value = newParamValue.split(',').map((s) => s.trim())
      }
    }

    setConfig((prev) => ({ ...prev, [fullKey]: value }))
    setNewParamKey('')
    setNewParamValue('')
    setShowAddParam(false)
  }, [newParamGroup, newParamKey, newParamType, newParamValue])

  // ── Toggle group collapse ───────────────────────────────────────
  const toggleGroup = useCallback((group: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(group)) next.delete(group)
      else next.add(group)
      return next
    })
  }, [])

  // ── Project change handler ──────────────────────────────────────
  const handleProjectChange = useCallback(
    (projectId: number | null) => {
      if (selectedProjectId && Object.keys(config).length > 0 && projectId !== selectedProjectId) {
        if (!confirm('Changing project will clear current config. Continue?')) return
      }
      setSelectedProjectId(projectId)
      setSelectedConfigPath(null)
      setParsedConfig(null)
      setConfig({})
      setOriginalConfig({})
    },
    [selectedProjectId, config],
  )

  // ── Config selection handler ────────────────────────────────────
  const handleConfigSelect = useCallback(
    (configPath: string | null) => {
      if (selectedConfigPath && Object.keys(config).length > 0 && changedKeys.size > 0) {
        if (!confirm('Switching config will discard your changes. Continue?')) return
      }
      setSelectedConfigPath(configPath)
      if (!configPath) {
        setParsedConfig(null)
        setConfig({})
        setOriginalConfig({})
      }
    },
    [selectedConfigPath, config, changedKeys],
  )

  // ── Tag management ──────────────────────────────────────────────
  const addTag = () => {
    const trimmed = tagInput.trim()
    if (trimmed && !tags.includes(trimmed)) {
      setTags([...tags, trimmed])
    }
    setTagInput('')
  }

  const removeTag = (tag: string) => setTags(tags.filter((t) => t !== tag))

  const handleTagKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTag()
    }
  }

  // ── Name change with debounced uniqueness check ────────────────
  const handleNameChange = useCallback(
    (newName: string) => {
      setName(newName)
      setNameError('')
      setNameSuggestion('')
      if (nameCheckTimer) clearTimeout(nameCheckTimer)
      if (!newName.trim()) return
      const timer = setTimeout(() => {
        const params = new URLSearchParams({ name: newName.trim() })
        if (selectedProjectId) params.set('project_id', String(selectedProjectId))
        if (isEditMode && editId) params.set('exclude_id', editId)
        client
          .get(`/experiments/check-name?${params}`)
          .then((res) => {
            if (!res.data.available) {
              setNameError('Name already exists')
              setNameSuggestion(res.data.suggestion || '')
            }
          })
          .catch(() => {})
      }, 500)
      setNameCheckTimer(timer)
    },
    [nameCheckTimer, selectedProjectId, isEditMode, editId],
  )

  // ── Save handlers ───────────────────────────────────────────────
  const buildPayload = (): ExperimentCreatePayload => ({
    name: name.trim(),
    description: description.trim() || undefined,
    config,
    project_id: selectedProjectId,
    base_config_path: selectedConfigPath,
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
      if (isEditMode && editId) {
        await client.put(`/experiments/${editId}`, buildPayload())
        navigate(`/experiments/${editId}`)
      } else {
        const res = await client.post('/experiments', buildPayload())
        navigate(`/experiments/${res.data.id}`)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save experiment')
    } finally {
      setSaving(false)
    }
  }

  const handleDryRun = async () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    setError('')
    setDryRunning(true)
    try {
      let expId = draftId
      if (!expId) {
        const createRes = await client.post('/experiments', buildPayload())
        expId = createRes.data.id
        setDraftId(expId)
      } else {
        await client.put(`/experiments/${expId}`, buildPayload())
      }
      const dryRes = await client.post(`/experiments/${expId}/dry-run`)
      setDryRunResult(dryRes.data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Dry run failed')
    } finally {
      setDryRunning(false)
    }
  }

  const handleConfirmStart = async () => {
    if (!draftId) return
    setSaving(true)
    try {
      await client.post(`/experiments/${draftId}/runs`)
      navigate(`/experiments/${draftId}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start training')
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
      let expId: number
      if (isEditMode && editId) {
        await client.put(`/experiments/${editId}`, buildPayload())
        expId = Number(editId)
      } else {
        const createRes = await client.post('/experiments', buildPayload())
        expId = createRes.data.id
      }
      await client.post(`/experiments/${expId}/start`)
      navigate(`/experiments/${expId}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save and start experiment')
    } finally {
      setSaving(false)
    }
  }

  // ── Diff computation ────────────────────────────────────────────
  const diffLines = useMemo(() => {
    if (!parsedConfig) return []
    const originalYaml = parsedConfig.raw_yaml
    const currentYaml = configToYaml(config)
    const origLines = originalYaml.split('\n')
    const currLines = currentYaml.split('\n')
    const maxLen = Math.max(origLines.length, currLines.length)
    const result: Array<{ type: 'same' | 'added' | 'removed' | 'changed'; original: string; current: string }> = []

    for (let i = 0; i < maxLen; i++) {
      const orig = origLines[i] ?? ''
      const curr = currLines[i] ?? ''
      if (orig === curr) {
        result.push({ type: 'same', original: orig, current: curr })
      } else if (!orig && curr) {
        result.push({ type: 'added', original: '', current: curr })
      } else if (orig && !curr) {
        result.push({ type: 'removed', original: orig, current: '' })
      } else {
        result.push({ type: 'changed', original: orig, current: curr })
      }
    }
    return result
  }, [parsedConfig, config])

  // ── Render ──────────────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-4xl">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-2xl font-bold text-foreground">
          {isEditMode ? 'Edit Experiment' : 'Create New Experiment'}
        </h1>
      </div>

      <div className="space-y-6">
        {/* ═══ Step 1: Project & Config Selection ═══════════════════ */}
        <section className="rounded-lg border border-border bg-card p-5">
          <h2 className="mb-4 flex items-center gap-2 text-base font-semibold text-card-foreground">
            <Layers className="h-4 w-4 text-primary" />
            Project &amp; Config
          </h2>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Project selector */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-card-foreground">
                Project <span className="text-destructive">*</span>
              </label>
              <select
                value={selectedProjectId ?? ''}
                onChange={(e) =>
                  handleProjectChange(e.target.value ? Number(e.target.value) : null)
                }
                disabled={projectsLoading}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="">
                  {projectsLoading ? 'Loading projects...' : 'Select a project'}
                </option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Config selector */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-card-foreground">
                Base Config
              </label>
              <select
                value={selectedConfigPath ?? ''}
                onChange={(e) => handleConfigSelect(e.target.value || null)}
                disabled={!selectedProjectId || availableConfigs.length === 0}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="">
                  {!selectedProjectId
                    ? 'Select a project first'
                    : availableConfigs.length === 0
                      ? 'No config files detected'
                      : 'Start from scratch'}
                </option>
                {availableConfigs.map((c) => (
                  <option key={c.path} value={c.path}>
                    {c.path} ({(c.size / 1024).toFixed(1)} KB)
                  </option>
                ))}
              </select>
            </div>

            {/* Experiment name */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-card-foreground">
                Experiment Name <span className="text-destructive">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="experiment-name"
                className={cn(
                  'w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring',
                  nameError ? 'border-destructive' : 'border-input',
                )}
              />
              {nameError && (
                <div className="mt-1 text-xs text-destructive">
                  {nameError}
                  {nameSuggestion && (
                    <button
                      type="button"
                      onClick={() => {
                        setName(nameSuggestion)
                        setNameError('')
                        setNameSuggestion('')
                      }}
                      className="ml-2 text-primary underline hover:no-underline"
                    >
                      Use &quot;{nameSuggestion}&quot;
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Description */}
            <div>
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

          {/* Parse loading indicator */}
          {parseLoading && (
            <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              Parsing config file...
            </div>
          )}
        </section>

        {/* ═══ Configuration Section ═══════════════════════════════ */}
        {(Object.keys(config).length > 0 || parsedConfig) && (
          <section className="rounded-lg border border-border bg-card">
            {/* View mode tabs */}
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <h2 className="text-base font-semibold text-card-foreground">Configuration</h2>
              <div className="flex items-center gap-1 rounded-md bg-muted p-0.5">
                <ViewTab
                  active={viewMode === 'form'}
                  onClick={() => setViewMode('form')}
                  icon={<FileText className="h-3.5 w-3.5" />}
                  label="Form"
                />
                <ViewTab
                  active={viewMode === 'yaml'}
                  onClick={() => setViewMode('yaml')}
                  icon={<Code className="h-3.5 w-3.5" />}
                  label="YAML"
                />
                <ViewTab
                  active={viewMode === 'diff'}
                  onClick={() => setViewMode('diff')}
                  icon={<GitCompare className="h-3.5 w-3.5" />}
                  label="Diff"
                  badge={changedKeys.size > 0 ? changedKeys.size : undefined}
                />
              </div>
            </div>

            <div className="p-4">
              {/* ── Form View ───────────────────────────────────── */}
              {viewMode === 'form' && (
                <div className="space-y-4">
                  {configGroups.map((group) => {
                    const isCollapsed = collapsedGroups.has(group.name)
                    const icon = GROUP_ICONS[group.name] || GROUP_ICONS.general

                    return (
                      <div key={group.name} className="rounded-md border border-border">
                        {/* Group header */}
                        <button
                          type="button"
                          onClick={() => toggleGroup(group.name)}
                          className="flex w-full items-center justify-between px-4 py-2.5 text-left transition-colors hover:bg-accent/50"
                        >
                          <span className="flex items-center gap-2 text-sm font-semibold text-card-foreground">
                            <span>{icon}</span>
                            <span className="capitalize">{group.name}</span>
                            <span className="text-xs font-normal text-muted-foreground">
                              ({group.fields.length})
                            </span>
                          </span>
                          <ChevronDown
                            className={cn(
                              'h-4 w-4 text-muted-foreground transition-transform',
                              isCollapsed && '-rotate-90',
                            )}
                          />
                        </button>

                        {/* Group fields */}
                        {!isCollapsed && (
                          <div className="space-y-3 border-t border-border px-4 py-3">
                            {group.fields.map((field: any) => {
                              const fullKey = field.fullKey
                              const value = config[fullKey] ?? field.value
                              const isChanged = changedKeys.has(fullKey)

                              return (
                                <ConfigField
                                  key={fullKey}
                                  label={field.key}
                                  fullKey={fullKey}
                                  value={value}
                                  type={field.type}
                                  isChanged={isChanged}
                                  isCopied={copiedKey === fullKey}
                                  onChange={(v) => handleConfigChange(fullKey, v)}
                                  onReset={() => handleResetField(fullKey)}
                                  onCopy={() => handleCopyValue(fullKey, value)}
                                  onDelete={() => handleDeleteField(fullKey)}
                                  disabled={saving}
                                />
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )
                  })}

                  {configGroups.length === 0 && (
                    <div className="rounded-lg border border-dashed border-border py-8 text-center">
                      <p className="text-sm text-muted-foreground">
                        {selectedProjectId
                          ? 'Select a config file above or add parameters manually.'
                          : 'Select a project and config file to get started.'}
                      </p>
                    </div>
                  )}

                  {/* Add parameter button */}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setShowAddParam(true)}
                      disabled={saving}
                      className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-input px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Plus className="h-4 w-4" />
                      Add Parameter
                    </button>
                    {Object.keys(config).length > 0 && (
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard.writeText(configToYaml(config))
                        }}
                        className="inline-flex items-center gap-1.5 rounded-md border border-input px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent"
                      >
                        <ClipboardCopy className="h-3.5 w-3.5" />
                        Copy YAML
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* ── YAML View ──────────────────────────────────── */}
              {viewMode === 'yaml' && (
                <div className="space-y-3">
                  <textarea
                    value={yamlText}
                    onChange={(e) => {
                      setYamlText(e.target.value)
                      setYamlError('')
                    }}
                    rows={Math.max(12, yamlText.split('\n').length + 2)}
                    spellCheck={false}
                    disabled={saving}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  {yamlError && (
                    <p className="text-xs text-destructive">Parse error: {yamlError}</p>
                  )}
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleYamlApply}
                      className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                    >
                      Apply Changes
                    </button>
                    <span className="text-xs text-muted-foreground">
                      Edit YAML above, then click Apply to sync with Form View
                    </span>
                  </div>
                </div>
              )}

              {/* ── Diff View ──────────────────────────────────── */}
              {viewMode === 'diff' && (
                <div>
                  {!parsedConfig ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      Diff view requires a base config. Select a config file to compare against.
                    </p>
                  ) : changedKeys.size === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      No changes from the original config.
                    </p>
                  ) : (
                    <div className="overflow-x-auto rounded-md border border-border font-mono text-xs">
                      {diffLines
                        .filter((line) => line.type !== 'same' || line.original.trim())
                        .map((line, i) => (
                          <div
                            key={i}
                            className={cn(
                              'flex border-b border-border/50 last:border-0',
                              line.type === 'added' && 'bg-green-500/10',
                              line.type === 'removed' && 'bg-red-500/10',
                              line.type === 'changed' && 'bg-yellow-500/10',
                            )}
                          >
                            <span className="w-6 flex-shrink-0 select-none border-r border-border/50 px-1 text-right text-muted-foreground/50">
                              {line.type === 'removed' ? '-' : line.type === 'added' ? '+' : line.type === 'changed' ? '~' : ' '}
                            </span>
                            <span
                              className={cn(
                                'flex-1 whitespace-pre px-2 py-0.5',
                                line.type === 'removed' && 'text-red-400 line-through',
                                line.type === 'added' && 'text-green-400',
                                line.type === 'changed' && 'text-yellow-400',
                              )}
                            >
                              {line.type === 'removed' || line.type === 'same'
                                ? line.original
                                : line.current}
                            </span>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>
        )}

        {/* ═══ Error ═══════════════════════════════════════════════ */}
        {error && (
          <div className="flex items-start gap-2 rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* ═══ Actions ═════════════════════════════════════════════ */}
        <div className="flex items-center justify-end gap-3 border-t border-border pt-4">
          <button
            type="button"
            onClick={() => navigate(-1)}
            disabled={saving}
            className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSaveDraft}
            disabled={saving || !name.trim() || !!nameError}
            className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {isEditMode ? 'Save Changes' : 'Save as Draft'}
          </button>
          <button
            type="button"
            onClick={handleDryRun}
            disabled={saving || dryRunning || !name.trim() || !!nameError}
            className="inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/5 px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Eye className="h-4 w-4" />
            {dryRunning ? 'Running...' : 'Dry Run'}
          </button>
          <button
            type="button"
            onClick={handleSaveAndStart}
            disabled={saving || !name.trim() || !!nameError}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className="h-4 w-4" />
            {isEditMode ? 'Save & Start Training' : 'Create & Start Training'}
          </button>
        </div>
      </div>

      {/* ═══ Add Parameter Dialog ═══════════════════════════════════ */}
      {showAddParam && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-lg">
            <h3 className="mb-4 text-lg font-semibold text-card-foreground">Add Parameter</h3>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">
                  Group
                </label>
                <input
                  type="text"
                  value={newParamGroup}
                  onChange={(e) => setNewParamGroup(e.target.value)}
                  placeholder="e.g. training, model, data"
                  list="existing-groups"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <datalist id="existing-groups">
                  {configGroups.map((g) => (
                    <option key={g.name} value={g.name} />
                  ))}
                </datalist>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">
                  Key <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  value={newParamKey}
                  onChange={(e) => setNewParamKey(e.target.value)}
                  placeholder="e.g. learning_rate"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">
                  Type
                </label>
                <select
                  value={newParamType}
                  onChange={(e) => setNewParamType(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="string">String</option>
                  <option value="integer">Integer</option>
                  <option value="float">Float</option>
                  <option value="boolean">Boolean</option>
                  <option value="array">Array</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">
                  Value
                </label>
                {newParamType === 'boolean' ? (
                  <select
                    value={newParamValue}
                    onChange={(e) => setNewParamValue(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                ) : (
                  <input
                    type={newParamType === 'integer' || newParamType === 'float' ? 'number' : 'text'}
                    step={newParamType === 'float' ? '0.001' : undefined}
                    value={newParamValue}
                    onChange={(e) => setNewParamValue(e.target.value)}
                    placeholder={
                      newParamType === 'array' ? '[1, 2, 3] or comma-separated' : 'value'
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                )}
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowAddParam(false)}
                className="rounded-md border border-input px-4 py-2 text-sm font-medium hover:bg-accent"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleAddParameter}
                disabled={!newParamKey.trim()}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                Add
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ Dry Run Preview Modal ═════════════════════════════════ */}
      {dryRunResult && (
        <DryRunModal
          result={dryRunResult}
          onConfirm={handleConfirmStart}
          onClose={() => setDryRunResult(null)}
          loading={saving}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ViewTab
// ---------------------------------------------------------------------------

function ViewTab({
  active,
  onClick,
  icon,
  label,
  badge,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
  badge?: number
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
        active
          ? 'bg-background text-foreground shadow-sm'
          : 'text-muted-foreground hover:text-foreground',
      )}
    >
      {icon}
      {label}
      {badge !== undefined && badge > 0 && (
        <span className="ml-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
          {badge}
        </span>
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// ConfigField
// ---------------------------------------------------------------------------

function ConfigField({
  label,
  fullKey: _fullKey,
  value,
  type,
  isChanged,
  isCopied,
  onChange,
  onReset,
  onCopy,
  onDelete,
  disabled,
}: {
  label: string
  fullKey: string
  value: unknown
  type?: string
  isChanged: boolean
  isCopied: boolean
  onChange: (value: unknown) => void
  onReset: () => void
  onCopy: () => void
  onDelete: () => void
  disabled?: boolean
}) {
  const inferredType = type || inferType(value)

  return (
    <div className="group flex items-start gap-3">
      {/* Label */}
      <div className="flex w-40 flex-shrink-0 flex-col pt-2">
        <span className="flex items-center gap-1.5 text-sm font-medium text-card-foreground">
          {label}
          {isChanged && (
            <span className="h-2 w-2 rounded-full bg-blue-500" title="Modified" />
          )}
        </span>
        <span className="text-[10px] text-muted-foreground">{inferredType}</span>
      </div>

      {/* Input */}
      <div className="min-w-0 flex-1">
        {inferredType === 'boolean' ? (
          <button
            type="button"
            onClick={() => onChange(!value)}
            disabled={disabled}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              value
                ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                : 'bg-muted text-muted-foreground hover:bg-muted/80',
            )}
          >
            {value ? 'true' : 'false'}
          </button>
        ) : inferredType === 'integer' ? (
          <input
            type="number"
            step={1}
            value={value as number}
            onChange={(e) => onChange(parseInt(e.target.value) || 0)}
            disabled={disabled}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
        ) : inferredType === 'float' ? (
          <input
            type="number"
            step={0.001}
            value={value as number}
            onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
            disabled={disabled}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
        ) : inferredType === 'array' ? (
          <input
            type="text"
            value={Array.isArray(value) ? value.join(', ') : String(value ?? '')}
            onChange={(e) => {
              const parts = e.target.value.split(',').map((s) => {
                const trimmed = s.trim()
                const num = Number(trimmed)
                return !isNaN(num) && trimmed !== '' ? num : trimmed
              })
              onChange(parts)
            }}
            disabled={disabled}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
        ) : inferredType === 'object' ? (
          <textarea
            value={typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '')}
            onChange={(e) => {
              try {
                onChange(JSON.parse(e.target.value))
              } catch {
                // Keep raw text until valid JSON
              }
            }}
            rows={3}
            disabled={disabled}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
        ) : (
          <input
            type="text"
            value={String(value ?? '')}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-shrink-0 items-center gap-0.5 pt-1.5 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          type="button"
          onClick={onCopy}
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          title={isCopied ? 'Copied!' : 'Copy value'}
        >
          <ClipboardCopy className="h-3.5 w-3.5" />
        </button>
        {isChanged && (
          <button
            type="button"
            onClick={onReset}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            title="Reset to original"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        )}
        <button
          type="button"
          onClick={onDelete}
          className="rounded p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
          title="Remove parameter"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// DryRunModal
// ---------------------------------------------------------------------------

function DryRunModal({
  result,
  onConfirm,
  onClose,
  loading,
}: {
  result: DryRunResult
  onConfirm: () => void
  onClose: () => void
  loading: boolean
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl rounded-lg border border-border bg-card p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-card-foreground">Dry Run Preview</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Command */}
        <div className="mb-4">
          <h4 className="mb-1 text-sm font-medium text-muted-foreground">Command</h4>
          <pre className="overflow-x-auto rounded-md bg-muted px-3 py-2 text-xs">
            {result.command.join(' ')}
          </pre>
        </div>

        {/* Working dir */}
        <div className="mb-4">
          <h4 className="mb-1 text-sm font-medium text-muted-foreground">Working Directory</h4>
          <code className="text-xs text-card-foreground">{result.working_dir}</code>
        </div>

        {/* Warnings */}
        {result.warnings.length > 0 && (
          <div className="mb-4 rounded-md bg-yellow-500/10 p-3">
            <h4 className="mb-1 flex items-center gap-1 text-sm font-medium text-yellow-500">
              <AlertTriangle className="h-4 w-4" />
              Warnings
            </h4>
            <ul className="list-inside list-disc text-xs text-yellow-400">
              {result.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Config YAML */}
        <div className="mb-4">
          <h4 className="mb-1 text-sm font-medium text-muted-foreground">Generated Config</h4>
          <pre className="max-h-60 overflow-auto rounded-md bg-muted px-3 py-2 text-xs">
            {result.config_yaml}
          </pre>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border border-input px-4 py-2 text-sm font-medium hover:bg-accent"
          >
            Close
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <Play className="h-4 w-4" />
            {loading ? 'Starting...' : 'Start Training'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function inferType(value: unknown): string {
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'number') return Number.isInteger(value) ? 'integer' : 'float'
  if (Array.isArray(value)) return 'array'
  if (typeof value === 'object' && value !== null) return 'object'
  return 'string'
}
