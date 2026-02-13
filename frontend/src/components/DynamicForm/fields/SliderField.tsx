import type { FieldProps } from '@/types/schema'

export default function SliderField({ field, value, onChange, disabled }: FieldProps) {
  const min = field.min ?? 0
  const max = field.max ?? 100
  const step = field.step ?? 1
  const current = typeof value === 'number' ? value : (field.default_value as number) ?? min

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <label className="text-sm font-medium text-card-foreground">
          {field.label || field.key}
          {field.required && <span className="ml-1 text-destructive">*</span>}
        </label>
        <span className="rounded bg-muted px-2 py-0.5 font-mono text-xs text-muted-foreground">
          {current}
        </span>
      </div>
      <input
        type="range"
        value={current}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
        min={min}
        max={max}
        step={step}
        className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-muted accent-primary disabled:cursor-not-allowed disabled:opacity-50"
      />
      <div className="mt-1 flex justify-between text-xs text-muted-foreground">
        <span>{min}</span>
        <span>{max}</span>
      </div>
      {field.description && (
        <p className="mt-1 text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  )
}
