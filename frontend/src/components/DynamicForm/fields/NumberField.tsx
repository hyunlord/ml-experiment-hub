import { useState } from 'react'
import { cn } from '@/lib/utils'
import type { FieldProps } from '@/types/schema'

export default function NumberField({ field, value, onChange, disabled, dependencyState }: FieldProps) {
  const [error, setError] = useState('')
  const isDepDisabled = disabled || (dependencyState?.disabled ?? false)

  const handleChange = (raw: string) => {
    if (raw === '' || raw === '-') {
      onChange(raw === '' ? undefined : raw)
      setError('')
      return
    }
    const num = Number(raw)
    if (isNaN(num)) return

    if (field.min !== undefined && num < field.min) {
      setError(`Min: ${field.min}`)
    } else if (field.max !== undefined && num > field.max) {
      setError(`Max: ${field.max}`)
    } else {
      setError('')
    }
    onChange(num)
  }

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-card-foreground">
        {field.label || field.key}
        {field.required && <span className="ml-1 text-destructive">*</span>}
      </label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value !== undefined && value !== null ? String(value) : (field.default_value !== undefined ? String(field.default_value) : '')}
          onChange={(e) => handleChange(e.target.value)}
          disabled={isDepDisabled}
          min={field.min}
          max={field.max}
          step={field.step ?? 'any'}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        />
        {(field.min !== undefined || field.max !== undefined) && (
          <span className="shrink-0 text-xs text-muted-foreground">
            [{field.min ?? '−∞'}, {field.max ?? '∞'}]
          </span>
        )}
      </div>
      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
      {!error && dependencyState?.hint && (
        <p className={cn(
          'mt-1 text-xs font-medium',
          dependencyState.disabled ? 'text-amber-500' : 'text-blue-500'
        )}>
          {dependencyState.hint}
        </p>
      )}
      {!error && !dependencyState?.hint && field.description && (
        <p className="mt-1 text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  )
}
