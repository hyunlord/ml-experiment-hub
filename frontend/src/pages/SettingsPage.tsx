import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle,
  Bell,
  Check,
  Clock,
  Cpu,
  Database,
  FolderOpen,
  Loader2,
  Plus,
  Save,
  Send,
  Server,
  Thermometer,
  Trash2,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react'
import { getSettings, updateSettings, testWebhook, type HubSettings } from '@/api/queue'
import {
  listServers,
  createServer,
  updateServer as updateServerApi,
  deleteServer,
  testServerConnection,
  type Server as ServerType,
  type ServerCreate,
  type ConnectionTestResult,
} from '@/api/servers'
import { useServerStore } from '@/stores/serverStore'
import { useSettingsStore } from '@/stores/settingsStore'
import { getDetectedTimezone } from '@/utils/time'

// ---------------------------------------------------------------------------
// Alert threshold defaults (stored in localStorage)
// ---------------------------------------------------------------------------

export interface AlertThresholds {
  gpu_temp_warn: number
  gpu_temp_crit: number
  gpu_mem_warn: number
  gpu_mem_crit: number
  ram_warn: number
  ram_crit: number
  disk_warn: number
  disk_crit: number
}

const DEFAULT_THRESHOLDS: AlertThresholds = {
  gpu_temp_warn: 80,
  gpu_temp_crit: 90,
  gpu_mem_warn: 90,
  gpu_mem_crit: 95,
  ram_warn: 85,
  ram_crit: 95,
  disk_warn: 85,
  disk_crit: 95,
}

export function loadThresholds(): AlertThresholds {
  try {
    const raw = localStorage.getItem('ml-hub-alert-thresholds')
    if (raw) return { ...DEFAULT_THRESHOLDS, ...JSON.parse(raw) }
  } catch { /* ignore */ }
  return { ...DEFAULT_THRESHOLDS }
}

function saveThresholds(t: AlertThresholds) {
  localStorage.setItem('ml-hub-alert-thresholds', JSON.stringify(t))
}

// ---------------------------------------------------------------------------
// Settings Page
// ---------------------------------------------------------------------------

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
    apiUrl: window.location.origin,
    gpuIds: '',
  })
  const [hub, setHub] = useState<HubSettings>({
    discord_webhook_url: '',
    slack_webhook_url: '',
    max_concurrent_runs: 1,
  })
  const [saved, setSaved] = useState(false)
  const [hubLoading, setHubLoading] = useState(true)
  const [testingDiscord, setTestingDiscord] = useState(false)
  const [testingSlack, setTestingSlack] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)

  // Servers
  const [servers, setServers] = useState<ServerType[]>([])
  const [serversLoading, setServersLoading] = useState(true)
  const [showAddServer, setShowAddServer] = useState(false)
  const [newServer, setNewServer] = useState<ServerCreate>({
    name: '',
    host: 'localhost',
    port: 8001,
    auth_type: 'none',
    api_key: '',
    description: '',
    tags: [],
    is_default: false,
    is_local: false,
  })
  const [testingServer, setTestingServer] = useState<number | null>(null)
  const [serverTestResult, setServerTestResult] = useState<Record<number, ConnectionTestResult>>({})
  const { fetchServers: refreshServerStore } = useServerStore()

  // Alert thresholds
  const [thresholds, setThresholds] = useState<AlertThresholds>(loadThresholds)

  // Timezone settings
  const { timezone, setTimezone } = useSettingsStore()

  // Load data
  useEffect(() => {
    getSettings()
      .then((data) => setHub(data))
      .catch(() => {})
      .finally(() => setHubLoading(false))
  }, [])

  const loadServers = useCallback(async () => {
    setServersLoading(true)
    try {
      const data = await listServers()
      setServers(data)
    } catch { /* ignore */ }
    setServersLoading(false)
  }, [])

  useEffect(() => { loadServers() }, [loadServers])

  const updateLocal = (key: keyof LocalSettings, value: string) => {
    setLocal((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  const updateHub_ = (key: keyof HubSettings, value: string | number) => {
    setHub((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  const handleSave = async () => {
    localStorage.setItem('ml-hub-settings', JSON.stringify(local))
    saveThresholds(thresholds)

    try {
      const updated = await updateSettings({
        discord_webhook_url: hub.discord_webhook_url,
        slack_webhook_url: hub.slack_webhook_url,
        max_concurrent_runs: hub.max_concurrent_runs,
      })
      setHub(updated)
    } catch { /* ignore */ }

    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleTestWebhook = async (provider: 'discord' | 'slack') => {
    const setter = provider === 'discord' ? setTestingDiscord : setTestingSlack
    setter(true)
    setTestResult(null)
    try {
      await updateSettings({
        discord_webhook_url: hub.discord_webhook_url,
        slack_webhook_url: hub.slack_webhook_url,
      })
      const result = await testWebhook(provider)
      if (result.ok) {
        setTestResult(`${provider} webhook sent successfully!`)
      } else {
        setTestResult(`${provider} webhook failed: ${result.error}`)
      }
    } catch {
      setTestResult(`Failed to test ${provider} webhook`)
    } finally {
      setter(false)
      setTimeout(() => setTestResult(null), 4000)
    }
  }

  // Server actions
  const handleAddServer = async () => {
    if (!newServer.name || !newServer.host) return
    try {
      await createServer(newServer)
      setShowAddServer(false)
      setNewServer({ name: '', host: 'localhost', port: 8001, auth_type: 'none', api_key: '', description: '', tags: [], is_default: false, is_local: false })
      await loadServers()
      refreshServerStore()
    } catch { /* ignore */ }
  }

  const handleDeleteServer = async (id: number) => {
    try {
      await deleteServer(id)
      await loadServers()
      refreshServerStore()
    } catch { /* ignore */ }
  }

  const handleTestServer = async (id: number) => {
    setTestingServer(id)
    try {
      const result = await testServerConnection(id)
      setServerTestResult((prev) => ({ ...prev, [id]: result }))
    } catch {
      setServerTestResult((prev) => ({ ...prev, [id]: { ok: false, latency_ms: null, error: 'Connection failed' } }))
    }
    setTestingServer(null)
  }

  const handleSetDefault = async (id: number) => {
    try {
      await updateServerApi(id, { is_default: true })
      await loadServers()
      refreshServerStore()
    } catch { /* ignore */ }
  }

  const updateThreshold = (key: keyof AlertThresholds, value: number) => {
    setThresholds((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="space-y-6">
        {/* ── Time Display ── */}
        <Section title="Time Display" icon={<Clock className="h-5 w-5" />}>
          <p className="text-xs text-muted-foreground">
            Choose how timestamps are displayed across the application.
          </p>
          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="radio"
                name="timezone"
                value="local"
                checked={timezone === 'local'}
                onChange={() => setTimezone('local')}
                className="h-4 w-4 text-primary focus:ring-2 focus:ring-ring"
              />
              <div>
                <span className="text-sm font-medium text-foreground">Local Time</span>
                <p className="text-xs text-muted-foreground">Use your browser's timezone</p>
              </div>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="radio"
                name="timezone"
                value="utc"
                checked={timezone === 'utc'}
                onChange={() => setTimezone('utc')}
                className="h-4 w-4 text-primary focus:ring-2 focus:ring-ring"
              />
              <div>
                <span className="text-sm font-medium text-foreground">UTC</span>
                <p className="text-xs text-muted-foreground">Display all times in Coordinated Universal Time</p>
              </div>
            </label>
          </div>
          <div className="mt-2 rounded-md bg-muted px-3 py-2">
            <p className="text-xs text-muted-foreground">
              Detected: <span className="font-medium text-foreground">{getDetectedTimezone()}</span>
            </p>
          </div>
        </Section>

        {/* ── Servers ── */}
        <Section title="Servers" icon={<Server className="h-5 w-5" />}>
          {serversLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading servers...
            </div>
          ) : (
            <>
              {servers.length === 0 && (
                <p className="text-sm text-muted-foreground">No servers registered yet.</p>
              )}
              <div className="space-y-2">
                {servers.map((s) => {
                  const test = serverTestResult[s.id]
                  return (
                    <div
                      key={s.id}
                      className="flex items-center justify-between rounded-md border border-border bg-background p-3"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm text-foreground">{s.name}</span>
                          {s.is_local && (
                            <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-blue-500">LOCAL</span>
                          )}
                          {s.is_default && (
                            <span className="rounded bg-green-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-green-500">DEFAULT</span>
                          )}
                          {test && (
                            test.ok
                              ? <span className="flex items-center gap-1 text-[10px] text-green-500"><Wifi className="h-3 w-3" />{test.latency_ms}ms</span>
                              : <span className="flex items-center gap-1 text-[10px] text-destructive"><WifiOff className="h-3 w-3" />{test.error}</span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">{s.host}:{s.port}{s.description ? ` — ${s.description}` : ''}</p>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleTestServer(s.id)}
                          disabled={testingServer === s.id}
                          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
                          title="Test connection"
                        >
                          {testingServer === s.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wifi className="h-4 w-4" />}
                        </button>
                        {!s.is_default && (
                          <button
                            onClick={() => handleSetDefault(s.id)}
                            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                            title="Set as default"
                          >
                            <Check className="h-4 w-4" />
                          </button>
                        )}
                        {!s.is_local && (
                          <button
                            onClick={() => handleDeleteServer(s.id)}
                            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-destructive"
                            title="Delete"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Add server form */}
              {showAddServer ? (
                <div className="space-y-3 rounded-md border border-border bg-background p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">Add Server</span>
                    <button onClick={() => setShowAddServer(false)} className="text-muted-foreground hover:text-foreground">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-card-foreground">Name</label>
                      <input
                        value={newServer.name}
                        onChange={(e) => setNewServer((p) => ({ ...p, name: e.target.value }))}
                        placeholder="Lab Server A"
                        className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-card-foreground">Host</label>
                      <input
                        value={newServer.host}
                        onChange={(e) => setNewServer((p) => ({ ...p, host: e.target.value }))}
                        placeholder="192.168.1.100"
                        className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-card-foreground">Port</label>
                      <input
                        type="number"
                        value={newServer.port}
                        onChange={(e) => setNewServer((p) => ({ ...p, port: parseInt(e.target.value) || 8001 }))}
                        className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-card-foreground">Auth Type</label>
                      <select
                        value={newServer.auth_type}
                        onChange={(e) => setNewServer((p) => ({ ...p, auth_type: e.target.value }))}
                        className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      >
                        <option value="none">None</option>
                        <option value="api_key">API Key</option>
                        <option value="ssh">SSH</option>
                      </select>
                    </div>
                  </div>
                  {newServer.auth_type === 'api_key' && (
                    <div>
                      <label className="mb-1 block text-xs font-medium text-card-foreground">API Key</label>
                      <input
                        type="password"
                        value={newServer.api_key}
                        onChange={(e) => setNewServer((p) => ({ ...p, api_key: e.target.value }))}
                        className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                  )}
                  <div>
                    <label className="mb-1 block text-xs font-medium text-card-foreground">Description</label>
                    <input
                      value={newServer.description}
                      onChange={(e) => setNewServer((p) => ({ ...p, description: e.target.value }))}
                      placeholder="GPU server in lab"
                      className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                  <button
                    onClick={handleAddServer}
                    disabled={!newServer.name || !newServer.host}
                    className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Add Server
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowAddServer(true)}
                  className="flex items-center gap-1.5 rounded-md border border-dashed border-border px-3 py-2 text-sm text-muted-foreground transition-colors hover:border-foreground hover:text-foreground"
                >
                  <Plus className="h-4 w-4" />
                  Add Server
                </button>
              )}
            </>
          )}
        </Section>

        {/* ── Alert Thresholds ── */}
        <Section title="Alert Thresholds" icon={<AlertTriangle className="h-5 w-5" />}>
          <p className="text-xs text-muted-foreground">
            Configure warning and critical thresholds for system monitoring alerts.
          </p>
          <ThresholdRow
            label="GPU Temperature"
            icon={<Thermometer className="h-4 w-4" />}
            warnValue={thresholds.gpu_temp_warn}
            critValue={thresholds.gpu_temp_crit}
            onWarnChange={(v) => updateThreshold('gpu_temp_warn', v)}
            onCritChange={(v) => updateThreshold('gpu_temp_crit', v)}
            unit="C"
            min={50}
            max={110}
          />
          <ThresholdRow
            label="GPU Memory"
            icon={<Cpu className="h-4 w-4" />}
            warnValue={thresholds.gpu_mem_warn}
            critValue={thresholds.gpu_mem_crit}
            onWarnChange={(v) => updateThreshold('gpu_mem_warn', v)}
            onCritChange={(v) => updateThreshold('gpu_mem_crit', v)}
            unit="%"
          />
          <ThresholdRow
            label="RAM Usage"
            icon={<Database className="h-4 w-4" />}
            warnValue={thresholds.ram_warn}
            critValue={thresholds.ram_crit}
            onWarnChange={(v) => updateThreshold('ram_warn', v)}
            onCritChange={(v) => updateThreshold('ram_crit', v)}
            unit="%"
          />
          <ThresholdRow
            label="Disk Usage"
            icon={<FolderOpen className="h-4 w-4" />}
            warnValue={thresholds.disk_warn}
            critValue={thresholds.disk_crit}
            onWarnChange={(v) => updateThreshold('disk_warn', v)}
            onCritChange={(v) => updateThreshold('disk_crit', v)}
            unit="%"
          />
        </Section>

        {/* ── Notifications ── */}
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
          {hub.discord_webhook_url && (
            <button
              onClick={() => handleTestWebhook('discord')}
              disabled={testingDiscord}
              className="flex items-center gap-1.5 rounded-md border border-input px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
            >
              <Send className="h-3.5 w-3.5" />
              {testingDiscord ? 'Sending...' : 'Test Discord Webhook'}
            </button>
          )}
          <Field
            label="Slack Webhook URL"
            description="Paste a Slack incoming webhook URL. Leave empty to disable."
            value={hub.slack_webhook_url}
            onChange={(v) => updateHub_('slack_webhook_url', v)}
            placeholder="https://hooks.slack.com/services/..."
            disabled={hubLoading}
          />
          {hub.slack_webhook_url && (
            <button
              onClick={() => handleTestWebhook('slack')}
              disabled={testingSlack}
              className="flex items-center gap-1.5 rounded-md border border-input px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
            >
              <Send className="h-3.5 w-3.5" />
              {testingSlack ? 'Sending...' : 'Test Slack Webhook'}
            </button>
          )}
          {testResult && (
            <p className={`text-xs ${testResult.includes('success') ? 'text-green-500' : 'text-destructive'}`}>
              {testResult}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Browser notifications are always enabled when the tab is in the background.
          </p>
        </Section>

        {/* ── Queue ── */}
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

        {/* ── Data paths ── */}
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

        {/* ── API ── */}
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

function ThresholdRow({
  label,
  icon,
  warnValue,
  critValue,
  onWarnChange,
  onCritChange,
  unit = '%',
  min = 0,
  max = 100,
}: {
  label: string
  icon: React.ReactNode
  warnValue: number
  critValue: number
  onWarnChange: (v: number) => void
  onCritChange: (v: number) => void
  unit?: string
  min?: number
  max?: number
}) {
  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-2 w-36">
        {icon}
        <span className="text-sm text-foreground">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-yellow-500">Warn</span>
        <input
          type="number"
          min={min}
          max={max}
          value={warnValue}
          onChange={(e) => onWarnChange(Math.max(min, Math.min(max, parseInt(e.target.value) || min)))}
          className="w-16 rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <span className="text-xs text-muted-foreground">{unit}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-destructive">Crit</span>
        <input
          type="number"
          min={min}
          max={max}
          value={critValue}
          onChange={(e) => onCritChange(Math.max(min, Math.min(max, parseInt(e.target.value) || min)))}
          className="w-16 rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <span className="text-xs text-muted-foreground">{unit}</span>
      </div>
    </div>
  )
}
