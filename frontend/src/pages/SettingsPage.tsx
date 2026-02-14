import { useEffect, useState } from 'react'
import { Bell, Cpu, Database, FolderOpen, Save } from 'lucide-react'
import { getSettings, updateSettings, type HubSettings } from '@/api/queue'

interface LocalSettings {
  dataRoot: string
  experimentDir: string
  apiUrl: string
  gpuIds: string
}

export default function SettingsPage() {
  const [local, setLocal] = useState<LocalSettings>({
    dataRoot: './data',
    experimentDir: './experiments',
    apiUrl: 'http://localhost:8000',
    gpuIds: '',
  })
  const [hub, setHub] = useState<HubSettings>({
    discord_webhook_url: '',
    max_concurrent_runs: 1,
  })
  const [saved, setSaved] = useState(false)
  const [hubLoading, setHubLoading] = useState(true)

  // Load hub settings from backend
  useEffect(() => {
    getSettings()
      .then((data) => setHub(data))
      .catch(() => {})
      .finally(() => setHubLoading(false))
  }, [])

  const updateLocal = (key: keyof LocalSettings, value: string) => {
    setLocal((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  const updateHub_ = (key: keyof HubSettings, value: string | number) => {
    setHub((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  const handleSave = async () => {
    // Save local settings
    localStorage.setItem('ml-hub-settings', JSON.stringify(local))

    // Save hub settings to backend
    try {
      const updated = await updateSettings({
        discord_webhook_url: hub.discord_webhook_url,
        max_concurrent_runs: hub.max_concurrent_runs,
      })
      setHub(updated)
    } catch {
      // ignore
    }

    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="space-y-6">
        {/* Notifications */}
        <Section
          title="Notifications"
          icon={<Bell className="h-5 w-5" />}
        >
          <Field
            label="Discord Webhook URL"
            description="Paste a Discord webhook URL to receive training notifications (start/complete/fail). Leave empty to disable."
            value={hub.discord_webhook_url}
            onChange={(v) => updateHub_('discord_webhook_url', v)}
            placeholder="https://discord.com/api/webhooks/..."
            disabled={hubLoading}
          />
          <p className="text-xs text-muted-foreground">
            Browser notifications are always enabled when the tab is in the background.
          </p>
        </Section>

        {/* Queue */}
        <Section
          title="Queue & Concurrency"
          icon={<Cpu className="h-5 w-5" />}
        >
          <div>
            <label className="mb-1 block text-sm font-medium text-card-foreground">
              Max Concurrent Runs
            </label>
            <p className="mb-1.5 text-xs text-muted-foreground">
              How many experiments can run simultaneously (default 1 for single GPU).
            </p>
            <input
              type="number"
              min={1}
              max={8}
              value={hub.max_concurrent_runs}
              onChange={(e) =>
                updateHub_('max_concurrent_runs', Math.max(1, parseInt(e.target.value) || 1))
              }
              className="w-24 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={hubLoading}
            />
          </div>
          <Field
            label="CUDA Visible Devices"
            description="Comma-separated GPU IDs (empty = all available)"
            value={local.gpuIds}
            onChange={(v) => updateLocal('gpuIds', v)}
            placeholder="0,1"
          />
        </Section>

        {/* Data paths */}
        <Section
          title="Data Paths"
          icon={<FolderOpen className="h-5 w-5" />}
        >
          <Field
            label="Data Root"
            description="Root directory for datasets (COCO, AI Hub, etc.)"
            value={local.dataRoot}
            onChange={(v) => updateLocal('dataRoot', v)}
          />
          <Field
            label="Experiment Directory"
            description="Where experiment configs and outputs are stored"
            value={local.experimentDir}
            onChange={(v) => updateLocal('experimentDir', v)}
          />
        </Section>

        {/* API */}
        <Section
          title="API Connection"
          icon={<Database className="h-5 w-5" />}
        >
          <Field
            label="API URL"
            description="Backend server URL"
            value={local.apiUrl}
            onChange={(v) => updateLocal('apiUrl', v)}
          />
        </Section>
      </div>

      <div className="mt-8 flex items-center gap-3">
        <button
          onClick={handleSave}
          className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Save className="h-4 w-4" />
          Save Settings
        </button>
        {saved && (
          <span className="text-sm text-green-500">Settings saved!</span>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function Section({
  title,
  icon,
  children,
}: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <h2 className="mb-4 flex items-center gap-2 text-base font-semibold text-card-foreground">
        {icon}
        {title}
      </h2>
      <div className="space-y-4">{children}</div>
    </div>
  )
}

function Field({
  label,
  description,
  value,
  onChange,
  placeholder,
  disabled,
}: {
  label: string
  description: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  disabled?: boolean
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-card-foreground">
        {label}
      </label>
      <p className="mb-1.5 text-xs text-muted-foreground">{description}</p>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
      />
    </div>
  )
}
