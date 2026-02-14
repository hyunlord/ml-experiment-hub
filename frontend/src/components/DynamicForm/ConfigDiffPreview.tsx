import { useMemo } from 'react'
import { cn } from '@/lib/utils'

interface ConfigDiffPreviewProps {
  current: Record<string, unknown>
  preset: Record<string, unknown>
}

export default function ConfigDiffPreview({ current, preset }: ConfigDiffPreviewProps) {
  const diff = useMemo(() => {
    const allKeys = new Set([...Object.keys(current), ...Object.keys(preset)])
    const lines: Array<{ key: string; status: 'added' | 'changed' | 'removed' | 'unchanged'; currentVal?: string; presetVal?: string }> = []

    for (const key of Array.from(allKeys).sort()) {
      const inCurrent = key in current
      const inPreset = key in preset
      const curVal = inCurrent ? formatValue(current[key]) : undefined
      const preVal = inPreset ? formatValue(preset[key]) : undefined

      if (inCurrent && !inPreset) {
        lines.push({ key, status: 'added', currentVal: curVal })
      } else if (!inCurrent && inPreset) {
        lines.push({ key, status: 'removed', presetVal: preVal })
      } else if (curVal !== preVal) {
        lines.push({ key, status: 'changed', currentVal: curVal, presetVal: preVal })
      } else {
        lines.push({ key, status: 'unchanged', currentVal: curVal })
      }
    }

    return lines
  }, [current, preset])

  const changedCount = diff.filter((d) => d.status !== 'unchanged').length

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        {changedCount === 0 ? '프리셋과 동일합니다' : `${changedCount}개 항목이 다릅니다`}
      </p>
      <div className="rounded-md border border-border bg-background font-mono text-xs">
        {diff.map((line) => (
          <div
            key={line.key}
            className={cn(
              'flex items-center gap-2 border-b border-border/50 px-3 py-1 last:border-b-0',
              line.status === 'added' && 'bg-green-500/10',
              line.status === 'changed' && 'bg-yellow-500/10',
              line.status === 'removed' && 'bg-red-500/10',
            )}
          >
            <span className={cn(
              'w-4 shrink-0 text-center font-bold',
              line.status === 'added' && 'text-green-600 dark:text-green-400',
              line.status === 'changed' && 'text-yellow-600 dark:text-yellow-400',
              line.status === 'removed' && 'text-red-600 dark:text-red-400',
            )}>
              {line.status === 'added' ? '+' : line.status === 'removed' ? '−' : line.status === 'changed' ? '~' : ' '}
            </span>
            <span className="min-w-[200px] text-muted-foreground">{line.key}:</span>
            {line.status === 'changed' ? (
              <span>
                <span className="text-red-500 line-through">{line.presetVal}</span>
                {' → '}
                <span className="text-green-600 dark:text-green-400">{line.currentVal}</span>
              </span>
            ) : line.status === 'removed' ? (
              <span className="text-red-500">{line.presetVal}</span>
            ) : (
              <span className={line.status === 'added' ? 'text-green-600 dark:text-green-400' : ''}>
                {line.currentVal}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return 'null'
  if (Array.isArray(val)) return `[${val.join(', ')}]`
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}
