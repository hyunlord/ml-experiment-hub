import { cn } from '@/lib/utils'
import type { FieldProps } from '@/types/schema'

export default function MultiSelectField({ field, value, onChange, disabled }: FieldProps) {
  const options = field.options ?? []
  const selected = Array.isArray(value) ? (value as string[]) : []

  const toggle = (opt: string) => {
    if (disabled) return
    const next = selected.includes(opt)
      ? selected.filter((v) => v !== opt)
      : [...selected, opt]
    onChange(next)
  }

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-card-foreground">
        {field.label || field.key}
        {field.required && <span className="ml-1 text-destructive">*</span>}
      </label>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = selected.includes(opt)
          return (
            <button
              key={opt}
              type="button"
              onClick={() => toggle(opt)}
              disabled={disabled}
              className={cn(
                'rounded-md border px-3 py-1.5 text-sm transition-colors',
                active
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-input bg-background text-foreground hover:bg-accent',
                disabled && 'cursor-not-allowed opacity-50',
              )}
            >
              {opt}
            </button>
          )
        })}
      </div>
      {selected.length > 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          {selected.length} selected
        </p>
      )}
      {field.description && (
        <p className="mt-1 text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  )
}
