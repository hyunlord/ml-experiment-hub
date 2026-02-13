import type { FieldProps } from '@/types/schema'

export default function TextField({ field, value, onChange, disabled }: FieldProps) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-card-foreground">
        {field.label || field.key}
        {field.required && <span className="ml-1 text-destructive">*</span>}
      </label>
      <input
        type="text"
        value={(value as string) ?? field.default_value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={field.placeholder || `Enter ${field.label || field.key}`}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      />
      {field.description && (
        <p className="mt-1 text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  )
}
