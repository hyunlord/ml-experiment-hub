import { cn } from '@/lib/utils'
import type { FieldProps } from '@/types/schema'

export default function BooleanField({ field, value, onChange, disabled }: FieldProps) {
  const checked = typeof value === 'boolean' ? value : (field.default_value as boolean) ?? false

  return (
    <div className="flex items-center justify-between gap-3">
      <div>
        <label className="text-sm font-medium text-card-foreground">
          {field.label || field.key}
          {field.required && <span className="ml-1 text-destructive">*</span>}
        </label>
        {field.description && (
          <p className="text-xs text-muted-foreground">{field.description}</p>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => !disabled && onChange(!checked)}
        disabled={disabled}
        className={cn(
          'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors',
          checked ? 'bg-primary' : 'bg-input',
          disabled && 'cursor-not-allowed opacity-50',
        )}
      >
        <span
          className={cn(
            'pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform',
            checked ? 'translate-x-5' : 'translate-x-0',
          )}
        />
      </button>
    </div>
  )
}
