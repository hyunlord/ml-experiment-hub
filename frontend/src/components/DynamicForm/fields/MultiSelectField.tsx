import { cn } from '@/lib/utils'
import type { FieldProps } from '@/types/schema'

export default function MultiSelectField({ field, value, onChange, disabled, dependencyState }: FieldProps) {
  const options = field.options ?? []
  const selected = Array.isArray(value) ? (value as string[]) : []

  const toggle = (optValue: string) => {
    if (disabled) return
    const next = selected.includes(optValue)
      ? selected.filter((v) => v !== optValue)
      : [...selected, optValue]
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
          const optValue = typeof opt === 'string' ? opt : opt.value
          const optLabel = typeof opt === 'string' ? opt : opt.label
          const optDesc = typeof opt === 'object' ? opt.description : undefined
          const active = selected.includes(optValue)
          return (
            <button
              key={optValue}
              type="button"
              onClick={() => toggle(optValue)}
              disabled={disabled}
              title={optDesc}
              className={cn(
                'rounded-md border px-3 py-1.5 text-sm transition-colors',
                active
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-input bg-background text-foreground hover:bg-accent',
                disabled && 'cursor-not-allowed opacity-50',
              )}
            >
              {optLabel}
            </button>
          )
        })}
      </div>
      {/* Dataset-specific hints for selected items */}
      {selected.length > 0 && (
        <div className="mt-1.5 space-y-0.5">
          <p className="text-xs text-muted-foreground">{selected.length}개 선택됨</p>
          {selected.includes('coco_ko') && (
            <p className="text-xs text-blue-500">coco_ko: COCO 이미지 재사용 — 추가 이미지 다운로드 불필요</p>
          )}
        </div>
      )}
      {dependencyState?.hint && (
        <p className="mt-1 text-xs font-medium text-amber-500">{dependencyState.hint}</p>
      )}
      {!dependencyState?.hint && !selected.length && field.description && (
        <p className="mt-1 text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  )
}
