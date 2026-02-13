import { Plus, Trash2 } from 'lucide-react'
import type { FieldProps } from '@/types/schema'

export default function ArrayField({ field, value, onChange, disabled }: FieldProps) {
  const items = Array.isArray(value) ? (value as unknown[]) : []

  const addItem = () => {
    const defaultVal = field.items_type === 'number' ? 0 : ''
    onChange([...items, defaultVal])
  }

  const removeItem = (index: number) => {
    onChange(items.filter((_, i) => i !== index))
  }

  const updateItem = (index: number, newVal: unknown) => {
    const updated = [...items]
    updated[index] = field.items_type === 'number' ? Number(newVal) : newVal
    onChange(updated)
  }

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <label className="text-sm font-medium text-card-foreground">
          {field.label || field.key}
          {field.required && <span className="ml-1 text-destructive">*</span>}
        </label>
        <span className="text-xs text-muted-foreground">{items.length} items</span>
      </div>

      <div className="space-y-2">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              type={field.items_type === 'number' ? 'number' : 'text'}
              value={String(item ?? '')}
              onChange={(e) => updateItem(i, e.target.value)}
              disabled={disabled}
              className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => removeItem(i)}
              disabled={disabled}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={addItem}
        disabled={disabled}
        className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-dashed border-input px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Plus className="h-3.5 w-3.5" />
        Add Item
      </button>

      {field.description && (
        <p className="mt-1 text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  )
}
