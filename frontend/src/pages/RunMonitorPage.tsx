import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Radio, Wifi, WifiOff } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useRunWebSocket } from '@/hooks/useRunWebSocket'
import type { MetricMessage, SystemMessage, LogMessage, HashAnalysisDetailMessage } from '@/components/RunMonitor/types'
import OverviewTab from '@/components/RunMonitor/OverviewTab'
import LossCurvesTab from '@/components/RunMonitor/LossCurvesTab'
import MetricsTab from '@/components/RunMonitor/MetricsTab'
import SystemTab from '@/components/RunMonitor/SystemTab'
import LogsTab from '@/components/RunMonitor/LogsTab'
import HashAnalysisTab from '@/components/RunMonitor/HashAnalysisTab'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'loss', label: 'Loss Curves' },
  { id: 'metrics', label: 'Metrics' },
  { id: 'system', label: 'System' },
  { id: 'logs', label: 'Logs' },
  { id: 'hash', label: 'Hash Analysis' },
] as const

type TabId = (typeof TABS)[number]['id']

export default function RunMonitorPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  // Three independent WebSocket channels
  // Raw messages from metrics channel (includes both metric and hash_analysis_detail)
  const {
    data: rawMetricsData,
    isConnected: metricsConnected,
  } = useRunWebSocket<MetricMessage | HashAnalysisDetailMessage>(runId ?? null, 'metrics')

  const {
    data: systemData,
    isConnected: systemConnected,
  } = useRunWebSocket<SystemMessage>(runId ?? null, 'system')

  const {
    data: logs,
    isConnected: logsConnected,
  } = useRunWebSocket<LogMessage>(runId ?? null, 'logs')

  // Split by type
  const metrics = useMemo(
    () => rawMetricsData.filter((m): m is MetricMessage => m.type === 'metric'),
    [rawMetricsData],
  )
  const hashDetails = useMemo(
    () => rawMetricsData.filter((m): m is HashAnalysisDetailMessage => m.type === 'hash_analysis_detail'),
    [rawMetricsData],
  )

  const anyConnected = metricsConnected || systemConnected || logsConnected

  // Derive run status from latest metric
  const lastMetric = metrics.length > 0 ? metrics[metrics.length - 1] : null
  const runStatus = lastMetric?.metrics?.['status'] != null
    ? String(lastMetric.metrics['status'])
    : anyConnected
      ? 'running'
      : 'connecting'

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-6 py-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-lg font-semibold text-foreground">
              Run #{runId}
            </h1>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Radio className={cn('h-3 w-3', anyConnected ? 'text-green-500' : 'text-red-500')} />
              <span>{runStatus}</span>
            </div>
          </div>
        </div>

        {/* Connection indicators */}
        <div className="flex items-center gap-3">
          <ConnectionBadge label="Metrics" connected={metricsConnected} />
          <ConnectionBadge label="System" connected={systemConnected} />
          <ConnectionBadge label="Logs" connected={logsConnected} />
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-border px-6">
        <nav className="-mb-px flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground',
              )}
            >
              {tab.label}
              {tab.id === 'logs' && logs.length > 0 && (
                <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-normal tabular-nums">
                  {logs.length}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'overview' && (
          <OverviewTab metrics={metrics} status={runStatus} />
        )}
        {activeTab === 'loss' && (
          <LossCurvesTab metrics={metrics} />
        )}
        {activeTab === 'metrics' && (
          <MetricsTab metrics={metrics} />
        )}
        {activeTab === 'system' && (
          <SystemTab systemData={systemData} />
        )}
        {activeTab === 'logs' && (
          <LogsTab logs={logs} />
        )}
        {activeTab === 'hash' && (
          <HashAnalysisTab metrics={metrics} hashDetails={hashDetails} />
        )}
      </div>
    </div>
  )
}

function ConnectionBadge({ label, connected }: { label: string; connected: boolean }) {
  return (
    <div className={cn(
      'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs',
      connected
        ? 'border-green-500/30 bg-green-500/10 text-green-600'
        : 'border-border bg-muted text-muted-foreground',
    )}>
      {connected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
      {label}
    </div>
  )
}
