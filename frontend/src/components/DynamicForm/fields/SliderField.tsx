import type { FieldProps } from '@/types/schema'

export default function SliderField({ field, value, onChange, disabled, dependencyState }: FieldProps) {
  const min = field.min ?? 0
  const max = field.max ?? 100
  const step = field.step ?? 1
  const current = typeof value === 'number' ? value : (field.default_value as number) ?? min
  const isDepDisabled = disabled || (dependencyState?.disabled ?? false)

  // Optuna range overlay calculation
  const optunaRange = field.optuna_range
  const optunaStyle = optunaRange
    ? {
        left: `${((optunaRange.min - min) / (max - min)) * 100}%`,
        width: `${((optunaRange.max - optunaRange.min) / (max - min)) * 100}%`,
      }
    : null

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

      {/* Slider with optional Optuna range overlay */}
      <div className="relative">
        {optunaStyle && (
          <div
            className="pointer-events-none absolute top-0 h-2 rounded-lg bg-primary/15"
            style={optunaStyle}
            title={`Optuna 탐색 범위: ${optunaRange!.min} ~ ${optunaRange!.max}`}
          />
        )}
        <input
          type="range"
          value={current}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={isDepDisabled}
          min={min}
          max={max}
          step={step}
          className="relative h-2 w-full cursor-pointer appearance-none rounded-lg bg-muted accent-primary disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>

      <div className="mt-1 flex justify-between text-xs text-muted-foreground">
        <span>{min}</span>
        {optunaRange && (
          <span className="text-primary/70">Optuna 탐색 범위: {optunaRange.min} ~ {optunaRange.max}</span>
        )}
        <span>{max}</span>
      </div>

      {/* Dependency hint */}
      {dependencyState?.hint && (
        <p className="mt-1 text-xs font-medium text-amber-500">{dependencyState.hint}</p>
      )}
      {!dependencyState?.hint && field.description && (
        <p className="mt-1 text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  )
}
