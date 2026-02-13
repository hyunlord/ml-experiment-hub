import { useState } from 'react'
import { FileUp, X } from 'lucide-react'

interface YamlImportProps {
  open: boolean
  onClose: () => void
  onImport: (config: Record<string, unknown>) => void
}

/**
 * Simple YAML-like paste import dialog.
 * Parses a subset of YAML (key: value per line, supports nested via indentation)
 * and converts to a flat dot-notation config object.
 */
export default function YamlImport({ open, onClose, onImport }: YamlImportProps) {
  const [raw, setRaw] = useState('')
  const [error, setError] = useState('')

  const handleImport = () => {
    setError('')
    try {
      const config = parseSimpleYaml(raw)
      onImport(config)
      setRaw('')
      onClose()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-lg border border-border bg-card p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-card-foreground">Import from YAML</h3>
          <button
            onClick={onClose}
            className="rounded-sm opacity-70 transition-opacity hover:opacity-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="mb-3 text-sm text-muted-foreground">
          Paste YAML or key-value pairs. Nested keys will be flattened to dot notation.
        </p>

        <textarea
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          rows={12}
          spellCheck={false}
          placeholder={`model:\n  backbone: resnet50\n  pretrained: true\ntraining:\n  batch_size: 32\n  learning_rate: 0.001`}
          className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />

        {error && <p className="mt-2 text-sm text-destructive">{error}</p>}

        <div className="mt-4 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleImport}
            disabled={!raw.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <FileUp className="h-4 w-4" />
            Import
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * Parse simple YAML-like text into a flat dot-notation object.
 * Handles nested indentation (2 or 4 spaces) and basic value types.
 */
function parseSimpleYaml(text: string): Record<string, unknown> {
  const lines = text.split('\n')
  const result: Record<string, unknown> = {}
  const stack: { indent: number; prefix: string }[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trimEnd()
    if (!trimmed || trimmed.startsWith('#')) continue

    const indent = line.length - line.trimStart().length
    const content = trimmed.trim()

    // Pop stack to find parent
    while (stack.length > 0 && stack[stack.length - 1].indent >= indent) {
      stack.pop()
    }

    const colonIdx = content.indexOf(':')
    if (colonIdx === -1) {
      throw new Error(`Line ${i + 1}: expected "key: value" format`)
    }

    const key = content.slice(0, colonIdx).trim()
    const rawValue = content.slice(colonIdx + 1).trim()
    const prefix = stack.length > 0 ? `${stack[stack.length - 1].prefix}.${key}` : key

    if (rawValue === '' || rawValue === '|' || rawValue === '>') {
      // Nested section
      stack.push({ indent, prefix })
    } else {
      // Leaf value
      result[prefix] = parseValue(rawValue)
    }
  }

  return result
}

function parseValue(raw: string): unknown {
  if (raw === 'true') return true
  if (raw === 'false') return false
  if (raw === 'null' || raw === '~') return null

  // Remove quotes
  if ((raw.startsWith('"') && raw.endsWith('"')) || (raw.startsWith("'") && raw.endsWith("'"))) {
    return raw.slice(1, -1)
  }

  // Try number
  const num = Number(raw)
  if (!isNaN(num) && raw !== '') return num

  // Array notation [a, b, c]
  if (raw.startsWith('[') && raw.endsWith(']')) {
    return raw
      .slice(1, -1)
      .split(',')
      .map((s) => parseValue(s.trim()))
  }

  return raw
}
