import { useCallback, useEffect, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { LogMessage } from './types'

interface LogsTabProps {
  logs: LogMessage[]
}

export default function LogsTab({ logs }: LogsTabProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchVisible, setSearchVisible] = useState(false)

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs.length, autoScroll])

  // Detect user scrolling away from bottom
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    const atBottom = scrollHeight - scrollTop - clientHeight < 50
    setAutoScroll(atBottom)
  }, [])

  // Keyboard shortcut: Ctrl+F for search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault()
        setSearchVisible(true)
      }
      if (e.key === 'Escape') {
        setSearchVisible(false)
        setSearchQuery('')
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const filteredLogs = searchQuery
    ? logs.filter((l) => l.line.toLowerCase().includes(searchQuery.toLowerCase()))
    : logs

  return (
    <div className="flex h-full flex-col">
      {/* Search bar */}
      {searchVisible && (
        <div className="mb-2 flex items-center gap-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search logs..."
            autoFocus
            className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <span className="text-xs text-muted-foreground">
            {searchQuery ? `${filteredLogs.length} matches` : `${logs.length} lines`}
          </span>
          <button
            onClick={() => {
              setSearchVisible(false)
              setSearchQuery('')
            }}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            ESC
          </button>
        </div>
      )}

      {/* Log container */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto rounded-lg border border-border bg-zinc-950 p-4 font-mono text-xs leading-5"
        style={{ minHeight: 400, maxHeight: 'calc(100vh - 280px)' }}
      >
        {filteredLogs.length === 0 ? (
          <span className="text-zinc-500">
            {logs.length === 0 ? 'Waiting for log output...' : 'No matches found'}
          </span>
        ) : (
          filteredLogs.map((log, i) => (
            <LogLine key={i} line={log.line} highlight={searchQuery} />
          ))
        )}
      </div>

      {/* Bottom bar */}
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {logs.length} lines
          {!searchVisible && (
            <> &middot; Press <kbd className="rounded border border-border px-1">Ctrl+F</kbd> to search</>
          )}
        </span>
        <button
          type="button"
          onClick={() => {
            setAutoScroll(true)
            if (containerRef.current) {
              containerRef.current.scrollTop = containerRef.current.scrollHeight
            }
          }}
          className={cn(
            'rounded-md px-2 py-1 text-xs transition-colors',
            autoScroll
              ? 'text-muted-foreground'
              : 'bg-primary/10 text-primary hover:bg-primary/20',
          )}
        >
          {autoScroll ? 'Auto-scroll ON' : 'Scroll to bottom'}
        </button>
      </div>
    </div>
  )
}

function LogLine({ line, highlight }: { line: string; highlight: string }) {
  const isError = /error|exception|traceback|fatal/i.test(line)
  const isWarning = /warn|warning/i.test(line)

  const colorClass = isError
    ? 'text-red-400'
    : isWarning
      ? 'text-yellow-400'
      : 'text-zinc-300'

  if (highlight) {
    const idx = line.toLowerCase().indexOf(highlight.toLowerCase())
    if (idx >= 0) {
      return (
        <div className={colorClass}>
          {line.slice(0, idx)}
          <span className="rounded bg-yellow-500/30 text-yellow-200">
            {line.slice(idx, idx + highlight.length)}
          </span>
          {line.slice(idx + highlight.length)}
        </div>
      )
    }
  }

  return <div className={colorClass}>{line}</div>
}
