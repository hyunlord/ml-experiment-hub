import { useState } from 'react'
import { Plus, X } from 'lucide-react'
import type { FieldDef, FieldType } from '@/types/schema'

const FIELD_TYPES: { value: FieldType; label: string }[] = [
  { value: 'text', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'select', label: 'Select' },
  { value: 'multi_select', label: 'Multi Select' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'slider', label: 'Slider' },
  { value: 'json', label: 'JSON' },
  { value: 'array', label: 'Array' },
]

interface AddFieldDialogProps {
  open: boolean
  onClose: () => void
  onAdd: (field: FieldDef) => void
}

export default function AddFieldDialog({ open, onClose, onAdd }: AddFieldDialogProps) {
  const [key, setKey] = useState('')
  const [type, setType] = useState<FieldType>('text')
  const [label, setLabel] = useState('')
  const [defaultValue, setDefaultValue] = useState('')
  const [options, setOptions] = useState('')

  const reset = () => {
    setKey('')
    setType('text')
    setLabel('')
    setDefaultValue('')
    setOptions('')
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!key.trim()) return

    const field: FieldDef = {
      key: key.trim(),
      type,
      label: label.trim() || undefined,
    }

    // Parse default value based on type
    if (defaultValue.trim()) {
      switch (type) {
        case 'number':
        case 'slider':
          field.default_value = Number(defaultValue)
          break
        case 'boolean':
          field.default_value = defaultValue.toLowerCase() === 'true'
          break
        case 'json':
          try {
            field.default_value = JSON.parse(defaultValue)
          } catch {
            field.default_value = defaultValue
          }
          break
        case 'array':
          field.default_value = defaultValue.split(',').map((s) => s.trim())
          break
        default:
          field.default_value = defaultValue
      }
    }

    // Parse options for select/multi_select
    if ((type === 'select' || type === 'multi_select') && options.trim()) {
      field.options = options.split(',').map((s) => s.trim()).filter(Boolean)
    }

    onAdd(field)
    reset()
    onClose()
  }

  if (!open) return null

  const showOptions = type === 'select' || type === 'multi_select'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-card-foreground">Add Parameter</h3>
          <button
            onClick={onClose}
            className="rounded-sm opacity-70 transition-opacity hover:opacity-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-card-foreground">
              Key <span className="text-muted-foreground">(dot notation)</span>
            </label>
            <input
              type="text"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              required
              placeholder="model.backbone"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-card-foreground">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as FieldType)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {FIELD_TYPES.map((ft) => (
                <option key={ft.value} value={ft.value}>
                  {ft.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-card-foreground">
              Label <span className="text-muted-foreground">(optional)</span>
            </label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Display label"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {showOptions && (
            <div>
              <label className="mb-1.5 block text-sm font-medium text-card-foreground">
                Options <span className="text-muted-foreground">(comma-separated)</span>
              </label>
              <input
                type="text"
                value={options}
                onChange={(e) => setOptions(e.target.value)}
                placeholder="option1, option2, option3"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          )}

          <div>
            <label className="mb-1.5 block text-sm font-medium text-card-foreground">
              Default Value <span className="text-muted-foreground">(optional)</span>
            </label>
            <input
              type="text"
              value={defaultValue}
              onChange={(e) => setDefaultValue(e.target.value)}
              placeholder={type === 'boolean' ? 'true / false' : 'default value'}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" />
              Add
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
