import { useState, useCallback } from 'react'
import type { FieldProps } from '@/types/schema'

export default function JsonField({ field, value, onChange, disabled }: FieldProps) {
  const [raw, setRaw] = useState(() => {
    try {
      return typeof value === 'string' ? value : JSON.stringify(value ?? field.default_value ?? {}, null, 2)
    } catch {
      return '{}'
    }
  })
  const [error, setError] = useState('')

  const handleChange = useCallback(
    (text: string) => {
      setRaw(text)
      try {
        const parsed = JSON.parse(text)
        setError('')
        onChange(parsed)
      } catch (e) {
        setError((e as Error).message)
      }
    },
    [onChange],
  )

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-card-foreground">
        {field.label || field.key}
        {field.required && <span className="ml-1 text-destructive">*</span>}
      </label>
      <textarea
        value={raw}
        onChange={(e) => handleChange(e.target.value)}
        disabled={disabled}
        rows={8}
        spellCheck={false}
        className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      />
      {error ? (
        <p className="mt-1 text-xs text-destructive">Invalid JSON: {error}</p>
      ) : (
        field.description && (
          <p className="mt-1 text-xs text-muted-foreground">{field.description}</p>
        )
      )}
    </div>
  )
}
