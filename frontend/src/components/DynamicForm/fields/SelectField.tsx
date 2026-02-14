import { cn } from '@/lib/utils'
import type { FieldProps } from '@/types/schema'

export default function SelectField({ field, value, onChange, disabled, dependencyState }: FieldProps) {
  const options = field.options ?? []
  const isDepDisabled = disabled || (dependencyState?.disabled ?? false)

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-card-foreground">
        {field.label || field.key}
        {field.required && <span className="ml-1 text-destructive">*</span>}
      </label>
      <select
        value={String(value ?? field.default_value ?? '')}
        onChange={(e) => onChange(e.target.value)}
        disabled={isDepDisabled}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">Select {field.label || field.key}...</option>
        {options.map((opt) => {
          const optValue = typeof opt === 'string' ? opt : opt.value
          const optLabel = typeof opt === 'string' ? opt : opt.label
          return (
            <option key={optValue} value={optValue}>
              {optLabel}
            </option>
          )
        })}
      </select>
      {dependencyState?.hint && (
        <p className={cn('mt-1 text-xs font-medium', dependencyState.disabled ? 'text-amber-500' : 'text-blue-500')}>
          {dependencyState.hint}
        </p>
      )}
      {!dependencyState?.hint && field.description && (
        <p className="mt-1 text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  )
}
