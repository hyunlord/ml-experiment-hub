import { useState, useMemo } from 'react'
import { ChevronDown, Plus, FileUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { DynamicFormProps, FieldDef } from '@/types/schema'
import FieldRenderer from './FieldRenderer'
import AddFieldDialog from './AddFieldDialog'
import YamlImport from './YamlImport'

/** Check if a dependency condition is met */
function isDependencyMet(
  dep: NonNullable<FieldDef['depends_on']>,
  values: Record<string, unknown>,
): boolean {
  const fieldValue = values[dep.field]
  if ('eq' in dep.condition) {
    return fieldValue === dep.condition.eq
  }
  return false
}

/** Compute warmup recommendation based on extra_datasets count */
function getWarmupRecommendation(
  extraDatasets: unknown,
  currentWarmup: unknown,
): string | undefined {
  if (!Array.isArray(extraDatasets) || extraDatasets.length === 0) return undefined
  const count = extraDatasets.length
  const recommended = 500 + count * 500
  const current = typeof currentWarmup === 'number' ? currentWarmup : 500
  if (current === recommended) return undefined
  return `데이터 ${count}개 선택 → 추천 warmup: ${recommended} (현재: ${current})`
}

/**
 * DynamicForm — renders a config form from a ConfigSchema's fields array.
 *
 * Two modes:
 * 1. Schema mode (schema !== null): renders fields grouped by `groups_order`
 * 2. Free-form mode (schema === null): "Add Parameter" + YAML import
 */
export default function DynamicForm({
  schema,
  values,
  onChange,
  onAddField,
  disabled,
  gpuAutoConfig,
}: DynamicFormProps) {
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [yamlDialogOpen, setYamlDialogOpen] = useState(false)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  // Group fields by their group property
  const { grouped, groupOrder } = useMemo(() => {
    if (!schema) return { grouped: new Map<string, FieldDef[]>(), groupOrder: [] as string[] }

    const map = new Map<string, FieldDef[]>()
    for (const field of schema.fields) {
      const group = field.group || 'General'
      if (!map.has(group)) map.set(group, [])
      map.get(group)!.push(field)
    }

    // Use explicit order or fallback to insertion order
    const order = schema.groups_order?.length
      ? schema.groups_order
      : Array.from(map.keys())

    return { grouped: map, groupOrder: order }
  }, [schema])

  const toggleGroup = (group: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(group)) next.delete(group)
      else next.add(group)
      return next
    })
  }

  const handleYamlImport = (config: Record<string, unknown>) => {
    for (const [key, value] of Object.entries(config)) {
      onChange(key, value)
    }
  }

  // Compute dependency state for a field
  const getDependencyState = (field: FieldDef): { disabled: boolean; hint?: string } | undefined => {
    if (!field.depends_on) return undefined
    const met = isDependencyMet(field.depends_on, values)
    if (!met) return undefined
    return {
      disabled: field.depends_on.effect === 'disabled',
      hint: field.depends_on.hint,
    }
  }

  // Compute extra hints for specific fields
  const getExtraHint = (field: FieldDef): string | undefined => {
    // Warmup recommendation based on extra_datasets
    if (field.key === 'training.warmup_steps') {
      return getWarmupRecommendation(values['data.extra_datasets'], values['training.warmup_steps'])
    }
    // GPU auto-config preview for batch_size=auto disabled fields
    if (gpuAutoConfig && values['training.batch_size'] === 'auto') {
      const isFrozen = values['model.freeze_backbone'] === true
      const autoValues = isFrozen ? gpuAutoConfig.frozen : gpuAutoConfig.unfrozen
      if (field.key === 'training.accumulate_grad_batches') {
        return `Auto: ${autoValues.accumulate_grad_batches} (batch ${autoValues.batch_size}×${autoValues.accumulate_grad_batches} = effective ${autoValues.batch_size * autoValues.accumulate_grad_batches})`
      }
      if (field.key === 'data.num_workers') {
        return `Auto: ${autoValues.num_workers} workers`
      }
    }
    return undefined
  }

  // ── Schema Mode ───────────────────────────────────────────────────
  if (schema) {
    return (
      <div className="space-y-4">
        {groupOrder.map((group) => {
          const fields = grouped.get(group)
          if (!fields?.length) return null

          const isCollapsed = collapsedGroups.has(group)

          return (
            <div
              key={group}
              className="rounded-lg border border-border bg-card"
            >
              {/* Group header (accordion toggle) */}
              <button
                type="button"
                onClick={() => toggleGroup(group)}
                className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-accent/50"
              >
                <span className="text-sm font-semibold text-card-foreground">
                  {group}
                </span>
                <ChevronDown
                  className={cn(
                    'h-4 w-4 text-muted-foreground transition-transform',
                    isCollapsed && '-rotate-90',
                  )}
                />
              </button>

              {/* Group body */}
              {!isCollapsed && (
                <div className="grid grid-cols-1 gap-4 border-t border-border px-4 py-4 md:grid-cols-2">
                  {fields.map((field) => {
                    const depState = getDependencyState(field)
                    const extraHint = getExtraHint(field)
                    const finalDepState = depState
                      ? { ...depState, hint: extraHint || depState.hint }
                      : extraHint
                        ? { disabled: false, hint: extraHint }
                        : undefined

                    return (
                      <div
                        key={field.key}
                        className={cn(
                          // Full-width for complex fields
                          (field.type === 'json' || field.type === 'array') &&
                            'md:col-span-2',
                        )}
                      >
                        <FieldRenderer
                          field={field}
                          value={values[field.key]}
                          onChange={(v) => onChange(field.key, v)}
                          disabled={disabled || (finalDepState?.disabled ?? false)}
                          dependencyState={finalDepState}
                        />
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  // ── Free-form Mode ────────────────────────────────────────────────
  const freeFields = Object.entries(values)

  return (
    <div className="space-y-4">
      {/* Existing free-form fields */}
      {freeFields.length > 0 && (
        <div className="rounded-lg border border-border bg-card">
          <div className="px-4 py-3">
            <span className="text-sm font-semibold text-card-foreground">
              Parameters
            </span>
          </div>
          <div className="grid grid-cols-1 gap-4 border-t border-border px-4 py-4 md:grid-cols-2">
            {freeFields.map(([key, val]) => {
              const inferredField = inferFieldDef(key, val)
              return (
                <div
                  key={key}
                  className={cn(
                    inferredField.type === 'json' && 'md:col-span-2',
                  )}
                >
                  <FieldRenderer
                    field={inferredField}
                    value={val}
                    onChange={(v) => onChange(key, v)}
                    disabled={disabled}
                  />
                </div>
              )
            })}
          </div>
        </div>
      )}

      {freeFields.length === 0 && (
        <div className="rounded-lg border border-dashed border-border bg-card/50 py-8 text-center">
          <p className="text-sm text-muted-foreground">
            No parameters yet. Add parameters manually or import from YAML.
          </p>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setAddDialogOpen(true)}
          disabled={disabled}
          className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-input px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          Add Parameter
        </button>
        <button
          type="button"
          onClick={() => setYamlDialogOpen(true)}
          disabled={disabled}
          className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-input px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          <FileUp className="h-4 w-4" />
          Import YAML
        </button>
      </div>

      {/* Dialogs */}
      <AddFieldDialog
        open={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        onAdd={(field) => {
          onAddField?.(field)
          onChange(field.key, field.default_value ?? getDefaultForType(field.type))
        }}
      />
      <YamlImport
        open={yamlDialogOpen}
        onClose={() => setYamlDialogOpen(false)}
        onImport={handleYamlImport}
      />
    </div>
  )
}

/** Infer a FieldDef from a key-value pair (for free-form rendering). */
function inferFieldDef(key: string, value: unknown): FieldDef {
  if (typeof value === 'boolean') return { key, type: 'boolean', label: key }
  if (typeof value === 'number') return { key, type: 'number', label: key }
  if (Array.isArray(value)) return { key, type: 'array', label: key }
  if (typeof value === 'object' && value !== null) return { key, type: 'json', label: key }
  return { key, type: 'text', label: key }
}

function getDefaultForType(type: string): unknown {
  switch (type) {
    case 'number':
    case 'slider':
      return 0
    case 'boolean':
      return false
    case 'json':
      return {}
    case 'array':
      return []
    case 'select':
    case 'multi_select':
      return type === 'multi_select' ? [] : ''
    default:
      return ''
  }
}
