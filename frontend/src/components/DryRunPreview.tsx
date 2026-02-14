import { AlertTriangle, Play, Terminal, X } from 'lucide-react'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DryRunResult {
  config_yaml: string
  command: string[]
  working_dir: string
  effective_config: Record<string, unknown>
  warnings: string[]
}

interface DryRunPreviewProps {
  result: DryRunResult
  onConfirm: () => void  // Start training
  onClose: () => void    // Go back to editing
  loading?: boolean      // While starting training
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DryRunPreview({
  result,
  onConfirm,
  onClose,
  loading = false,
}: DryRunPreviewProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="relative mx-4 flex h-[90vh] w-full max-w-4xl flex-col rounded-lg border border-border bg-card shadow-lg">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-xl font-semibold text-card-foreground">Dry Run Preview</h2>
          <button
            onClick={onClose}
            disabled={loading}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content - scrollable */}
        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-4">
          {/* Warnings section */}
          {result.warnings && result.warnings.length > 0 && (
            <div className="rounded-md border border-amber-500/50 bg-amber-500/10 px-4 py-3">
              <div className="mb-2 flex items-center gap-2 text-amber-600 dark:text-amber-500">
                <AlertTriangle className="h-5 w-5" />
                <span className="font-semibold">Warnings</span>
              </div>
              <ul className="space-y-1 text-sm text-amber-700 dark:text-amber-400">
                {result.warnings.map((warning, idx) => (
                  <li key={idx} className="ml-7">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Command section */}
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
              <Terminal className="h-4 w-4" />
              <span>Training Command</span>
            </div>
            <div className="rounded-md border border-border bg-muted px-4 py-3">
              <code className="block break-all font-mono text-sm text-foreground">
                {result.command.join(' ')}
              </code>
            </div>
          </div>

          {/* Working directory */}
          <div>
            <div className="mb-1 text-sm font-medium text-muted-foreground">
              Working Directory
            </div>
            <div className="rounded-md bg-muted px-3 py-1.5">
              <code className="font-mono text-xs text-foreground">{result.working_dir}</code>
            </div>
          </div>

          {/* Config YAML */}
          <div>
            <div className="mb-2 text-sm font-semibold text-foreground">
              Generated YAML Configuration
            </div>
            <div className="rounded-md border border-border bg-background">
              <textarea
                value={result.config_yaml}
                readOnly
                rows={Math.min(20, result.config_yaml.split('\n').length + 2)}
                spellCheck={false}
                className="w-full resize-none rounded-md border-0 bg-transparent px-4 py-3 font-mono text-sm text-foreground focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-end gap-3 border-t border-border px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            Back to Edit
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50',
            )}
          >
            <Play className="h-4 w-4" />
            {loading ? 'Starting...' : 'Start Training'}
          </button>
        </div>
      </div>
    </div>
  )
}
