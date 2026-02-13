import { useState } from 'react'
import { Database, FolderOpen, Cpu, Save } from 'lucide-react'

interface SettingsForm {
  dataRoot: string
  experimentDir: string
  apiUrl: string
  gpuIds: string
}

export default function SettingsPage() {
  const [form, setForm] = useState<SettingsForm>({
    dataRoot: './data',
    experimentDir: './experiments',
    apiUrl: 'http://localhost:8000',
    gpuIds: '',
  })
  const [saved, setSaved] = useState(false)

  const update = (key: keyof SettingsForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  const handleSave = () => {
    // TODO: Persist to backend /api/settings endpoint
    localStorage.setItem('ml-hub-settings', JSON.stringify(form))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="space-y-6">
        {/* Data paths */}
        <Section
          title="Data Paths"
          icon={<FolderOpen className="h-5 w-5" />}
        >
          <Field
            label="Data Root"
            description="Root directory for datasets (COCO, AI Hub, etc.)"
            value={form.dataRoot}
            onChange={(v) => update('dataRoot', v)}
          />
          <Field
            label="Experiment Directory"
            description="Where experiment configs and outputs are stored"
            value={form.experimentDir}
            onChange={(v) => update('experimentDir', v)}
          />
        </Section>

        {/* GPU */}
        <Section title="GPU Configuration" icon={<Cpu className="h-5 w-5" />}>
          <Field
            label="CUDA Visible Devices"
            description="Comma-separated GPU IDs (empty = all available)"
            value={form.gpuIds}
            onChange={(v) => update('gpuIds', v)}
            placeholder="0,1"
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
            value={form.apiUrl}
            onChange={(v) => update('apiUrl', v)}
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
}: {
  label: string
  description: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
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
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      />
    </div>
  )
}
