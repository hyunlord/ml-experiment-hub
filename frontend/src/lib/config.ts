/**
 * Config utilities for dot-notation ↔ nested dict ↔ YAML conversions.
 */

/** Flatten a nested object to dot-notation keys. */
export function flattenConfig(
  obj: Record<string, unknown>,
  prefix = '',
): Record<string, unknown> {
  const result: Record<string, unknown> = {}

  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key

    if (
      value !== null &&
      typeof value === 'object' &&
      !Array.isArray(value)
    ) {
      Object.assign(result, flattenConfig(value as Record<string, unknown>, fullKey))
    } else {
      result[fullKey] = value
    }
  }

  return result
}

/** Unflatten dot-notation keys into a nested object. */
export function unflattenConfig(
  flat: Record<string, unknown>,
): Record<string, unknown> {
  const result: Record<string, unknown> = {}

  for (const [key, value] of Object.entries(flat)) {
    const parts = key.split('.')
    let current = result

    for (let i = 0; i < parts.length - 1; i++) {
      if (!(parts[i] in current) || typeof current[parts[i]] !== 'object') {
        current[parts[i]] = {}
      }
      current = current[parts[i]] as Record<string, unknown>
    }

    current[parts[parts.length - 1]] = value
  }

  return result
}

/** Convert a flat dot-notation config to YAML string. */
export function configToYaml(flat: Record<string, unknown>): string {
  const nested = unflattenConfig(flat)
  return objectToYaml(nested, 0)
}

function objectToYaml(obj: unknown, indent: number): string {
  if (obj === null || obj === undefined) return 'null'
  if (typeof obj === 'boolean') return obj ? 'true' : 'false'
  if (typeof obj === 'number') return String(obj)
  if (typeof obj === 'string') {
    // Quote strings that could be ambiguous
    if (/^[\d.]+$/.test(obj) || ['true', 'false', 'null', '~', ''].includes(obj)) {
      return `"${obj}"`
    }
    if (obj.includes(':') || obj.includes('#') || obj.includes('\n')) {
      return `"${obj.replace(/"/g, '\\"')}"`
    }
    return obj
  }

  if (Array.isArray(obj)) {
    if (obj.length === 0) return '[]'
    const pad = '  '.repeat(indent)
    return obj.map((item) => `\n${pad}- ${objectToYaml(item, indent + 1)}`).join('')
  }

  if (typeof obj === 'object') {
    const entries = Object.entries(obj as Record<string, unknown>)
    if (entries.length === 0) return '{}'
    const pad = '  '.repeat(indent)
    return entries
      .map(([key, value]) => {
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
          return `${indent > 0 ? '\n' : ''}${pad}${key}:\n${objectToYaml(value, indent + 1).replace(/^\n/, '')}`
        }
        if (Array.isArray(value)) {
          return `${indent > 0 ? '\n' : ''}${pad}${key}:${objectToYaml(value, indent + 1)}`
        }
        return `${indent > 0 ? '\n' : ''}${pad}${key}: ${objectToYaml(value, indent + 1)}`
      })
      .join('')
  }

  return String(obj)
}

/** Parse simple YAML back to flat dot-notation config. */
export function yamlToConfig(yaml: string): Record<string, unknown> {
  const lines = yaml.split('\n')
  const result: Record<string, unknown> = {}
  const stack: { indent: number; prefix: string }[] = []

  for (const line of lines) {
    const trimmed = line.trimEnd()
    if (!trimmed || trimmed.trimStart().startsWith('#')) continue

    const indent = line.length - line.trimStart().length
    const content = trimmed.trim()

    while (stack.length > 0 && stack[stack.length - 1].indent >= indent) {
      stack.pop()
    }

    const colonIdx = content.indexOf(':')
    if (colonIdx === -1) continue

    const key = content.slice(0, colonIdx).trim()
    if (key.startsWith('-')) continue // Skip array items for now

    const rawValue = content.slice(colonIdx + 1).trim()
    const prefix = stack.length > 0 ? `${stack[stack.length - 1].prefix}.${key}` : key

    if (rawValue === '' || rawValue === '|' || rawValue === '>') {
      stack.push({ indent, prefix })
    } else {
      result[prefix] = parseYamlValue(rawValue)
    }
  }

  return result
}

function parseYamlValue(raw: string): unknown {
  if (raw === 'true') return true
  if (raw === 'false') return false
  if (raw === 'null' || raw === '~') return null

  if ((raw.startsWith('"') && raw.endsWith('"')) || (raw.startsWith("'") && raw.endsWith("'"))) {
    return raw.slice(1, -1)
  }

  const num = Number(raw)
  if (!isNaN(num) && raw !== '') return num

  if (raw.startsWith('[') && raw.endsWith(']')) {
    return raw
      .slice(1, -1)
      .split(',')
      .map((s) => parseYamlValue(s.trim()))
  }

  return raw
}
