import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  FolderGit2,
  GitBranch,
  Terminal,
  FileCode,
  FileText,
  Trash2,
  RefreshCw,
  Copy,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  FlaskConical,
  Plus,
  Edit,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  getProject,
  getProjectGitInfo,
  getConfigContent,
  rescanProject,
  deleteProject,
} from '@/api/projects'
import type { Project, GitInfo, ConfigContent } from '@/types/project'
import { ProjectStatus } from '@/types/project'

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [project, setProject] = useState<Project | null>(null)
  const [gitInfo, setGitInfo] = useState<GitInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [gitLoading, setGitLoading] = useState(false)
  const [rescanning, setRescanning] = useState(false)

  // Expanded config content
  const [expandedConfig, setExpandedConfig] = useState<Record<string, ConfigContent>>({})
  const [loadingConfig, setLoadingConfig] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!id) return
    fetchProject()
    fetchGitInfo()
  }, [id])

  const fetchProject = async () => {
    if (!id) return
    setLoading(true)
    try {
      const data = await getProject(id)
      setProject(data)
    } catch (error) {
      console.error('Failed to fetch project:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchGitInfo = async () => {
    if (!id) return
    setGitLoading(true)
    try {
      const data = await getProjectGitInfo(id)
      setGitInfo(data)
    } catch (error) {
      // Git info may not be available for all projects
      setGitInfo(null)
    } finally {
      setGitLoading(false)
    }
  }

  const handleCopyPath = () => {
    if (project?.path) {
      navigator.clipboard.writeText(project.path)
    }
  }

  const handleRescan = async () => {
    if (!id) return
    setRescanning(true)
    try {
      const updated = await rescanProject(id)
      setProject(updated)
    } catch (error) {
      console.error('Failed to rescan project:', error)
    } finally {
      setRescanning(false)
    }
  }

  const handleDelete = async () => {
    if (!id || !confirm('Delete this project? This cannot be undone.')) return
    try {
      await deleteProject(id)
      navigate('/projects')
    } catch (error) {
      console.error('Failed to delete project:', error)
    }
  }

  const toggleConfigContent = async (configPath: string) => {
    if (!id) return

    // If already expanded, collapse it
    if (expandedConfig[configPath]) {
      setExpandedConfig((prev) => {
        const next = { ...prev }
        delete next[configPath]
        return next
      })
      return
    }

    // Otherwise, fetch and expand
    setLoadingConfig((prev) => ({ ...prev, [configPath]: true }))
    try {
      const content = await getConfigContent(id, configPath)
      setExpandedConfig((prev) => ({ ...prev, [configPath]: content }))
    } catch (error) {
      console.error('Failed to fetch config content:', error)
    } finally {
      setLoadingConfig((prev) => ({ ...prev, [configPath]: false }))
    }
  }

  if (loading && !project) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading project...</p>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Project not found</p>
      </div>
    )
  }

  const statusConfig: Record<ProjectStatus, { label: string; classes: string }> = {
    [ProjectStatus.REGISTERED]: { label: 'Registered', classes: 'bg-blue-500/20 text-blue-300 border-blue-500/30' },
    [ProjectStatus.SCANNING]: { label: 'Scanning', classes: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30' },
    [ProjectStatus.READY]: { label: 'Ready', classes: 'bg-green-500/20 text-green-300 border-green-500/30' },
    [ProjectStatus.ERROR]: { label: 'Error', classes: 'bg-red-500/20 text-red-300 border-red-500/30' },
  }

  const status = statusConfig[project.status] || statusConfig[ProjectStatus.REGISTERED]

  return (
    <div>
      {/* Header */}
      <div className="mb-6 rounded-lg border border-border bg-card p-6">
        <div className="mb-4 flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold text-card-foreground">{project.name}</h1>
              <span className={cn('inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase', status.classes)}>
                {status.label}
              </span>
              <span className="inline-flex items-center rounded-full border border-input bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
                {project.project_type}
              </span>
            </div>
            {project.description && (
              <p className="mt-2 text-muted-foreground">{project.description}</p>
            )}
            <div className="mt-3 flex items-center gap-2 text-sm">
              <FolderGit2 className="h-4 w-4 text-muted-foreground" />
              <code className="rounded bg-secondary px-2 py-0.5 text-xs font-mono text-secondary-foreground">
                {project.path}
              </code>
              <button
                onClick={handleCopyPath}
                className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                title="Copy path"
              >
                <Copy className="h-3.5 w-3.5" />
              </button>
            </div>
            {project.git_url && (
              <div className="mt-2 flex items-center gap-2 text-sm">
                <GitBranch className="h-4 w-4 text-muted-foreground" />
                <a
                  href={project.git_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-primary hover:underline"
                >
                  {project.git_url}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => navigate(`/projects/${id}/edit`)}
            className="flex items-center gap-2 rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            <Edit className="h-4 w-4" />
            Edit
          </button>
          <button
            onClick={handleRescan}
            disabled={rescanning}
            className="flex items-center gap-2 rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
          >
            <RefreshCw className={cn('h-4 w-4', rescanning && 'animate-spin')} />
            Re-scan
          </button>
          <button
            onClick={handleDelete}
            className="flex items-center gap-2 rounded-md border border-destructive bg-background px-4 py-2 text-sm font-medium text-destructive transition-colors hover:bg-destructive hover:text-destructive-foreground"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        </div>
      </div>

      {/* Info Cards Row */}
      <div className="mb-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Python Env */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">Python Environment</h3>
          <p className="text-sm font-semibold text-card-foreground">{project.python_env}</p>
          {project.env_path && (
            <p className="mt-1 truncate text-xs text-muted-foreground" title={project.env_path}>
              {project.env_path}
            </p>
          )}
        </div>

        {/* Train Command */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">Train Command</h3>
          <code className="block truncate text-xs font-mono text-card-foreground" title={project.train_command_template}>
            {project.train_command_template}
          </code>
        </div>

        {/* Eval Command */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">Eval Command</h3>
          <code className="block truncate text-xs font-mono text-card-foreground" title={project.eval_command_template || 'Not set'}>
            {project.eval_command_template || <span className="text-muted-foreground">Not set</span>}
          </code>
        </div>

        {/* Directories */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">Directories</h3>
          <div className="space-y-1 text-xs">
            <div>
              <span className="text-muted-foreground">Config: </span>
              <span className="font-mono text-card-foreground">{project.config_dir}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Checkpoint: </span>
              <span className="font-mono text-card-foreground">{project.checkpoint_dir}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Detected Config Files */}
      {project.detected_configs.length > 0 && (
        <div className="mb-6 rounded-lg border border-border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold text-card-foreground">Detected Config Files</h2>
          <div className="space-y-2">
            {project.detected_configs.map((config) => {
              const isExpanded = !!expandedConfig[config.path]
              const isLoading = loadingConfig[config.path]
              const sizeKB = (config.size / 1024).toFixed(1)

              return (
                <div key={config.path} className="rounded-md border border-border bg-background">
                  <div className="flex items-center justify-between px-4 py-3">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => toggleConfigContent(config.path)}
                        className="text-muted-foreground transition-colors hover:text-foreground"
                        disabled={isLoading}
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </button>
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <code className="text-sm font-mono text-foreground">{config.path}</code>
                      <span className="rounded bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
                        {config.format}
                      </span>
                      <span className="text-xs text-muted-foreground">{sizeKB} KB</span>
                    </div>
                    <button
                      onClick={() => navigate(`/experiments/new?project_id=${id}&config=${encodeURIComponent(config.path)}`)}
                      className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Create Experiment
                    </button>
                  </div>
                  {isExpanded && expandedConfig[config.path] && (
                    <div className="border-t border-border px-4 py-3">
                      <pre className="overflow-x-auto rounded-md bg-secondary p-3 text-xs">
                        {expandedConfig[config.path].content}
                      </pre>
                    </div>
                  )}
                  {isLoading && (
                    <div className="border-t border-border px-4 py-3">
                      <p className="text-xs text-muted-foreground">Loading...</p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Detected Scripts */}
      <div className="mb-6 rounded-lg border border-border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold text-card-foreground">Detected Scripts</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {/* Train Scripts */}
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Terminal className="h-4 w-4" />
              Train Scripts
            </h3>
            {project.detected_scripts.train.length > 0 ? (
              <ul className="space-y-1">
                {project.detected_scripts.train.map((script) => (
                  <li key={script} className="flex items-center gap-2 text-sm">
                    <FileCode className="h-3.5 w-3.5 text-muted-foreground" />
                    <code className="truncate font-mono text-xs text-foreground" title={script}>
                      {script}
                    </code>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">None detected</p>
            )}
          </div>

          {/* Eval Scripts */}
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <FlaskConical className="h-4 w-4" />
              Eval Scripts
            </h3>
            {project.detected_scripts.eval.length > 0 ? (
              <ul className="space-y-1">
                {project.detected_scripts.eval.map((script) => (
                  <li key={script} className="flex items-center gap-2 text-sm">
                    <FileCode className="h-3.5 w-3.5 text-muted-foreground" />
                    <code className="truncate font-mono text-xs text-foreground" title={script}>
                      {script}
                    </code>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">None detected</p>
            )}
          </div>

          {/* Other Scripts */}
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <FileCode className="h-4 w-4" />
              Other Scripts
            </h3>
            {project.detected_scripts.other.length > 0 ? (
              <ul className="space-y-1">
                {project.detected_scripts.other.map((script) => (
                  <li key={script} className="flex items-center gap-2 text-sm">
                    <FileCode className="h-3.5 w-3.5 text-muted-foreground" />
                    <code className="truncate font-mono text-xs text-foreground" title={script}>
                      {script}
                    </code>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">None detected</p>
            )}
          </div>
        </div>
      </div>

      {/* Git Information */}
      {project.git_url && (
        <div className="mb-6 rounded-lg border border-border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold text-card-foreground">Git Information</h2>
          {gitLoading ? (
            <p className="text-sm text-muted-foreground">Loading git info...</p>
          ) : gitInfo ? (
            <div className="grid gap-3 md:grid-cols-2">
              {gitInfo.branch && (
                <div>
                  <h3 className="mb-1 text-sm font-medium text-muted-foreground">Branch</h3>
                  <p className="flex items-center gap-2 text-sm text-card-foreground">
                    <GitBranch className="h-4 w-4" />
                    {gitInfo.branch}
                  </p>
                </div>
              )}
              {gitInfo.last_commit_hash && (
                <div>
                  <h3 className="mb-1 text-sm font-medium text-muted-foreground">Last Commit</h3>
                  <p className="text-sm">
                    <code className="font-mono text-xs text-card-foreground">{gitInfo.last_commit_hash.substring(0, 7)}</code>
                  </p>
                  {gitInfo.last_commit_message && (
                    <p className="mt-1 text-xs text-muted-foreground">{gitInfo.last_commit_message}</p>
                  )}
                  {gitInfo.last_commit_date && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {new Date(gitInfo.last_commit_date).toLocaleString()}
                    </p>
                  )}
                </div>
              )}
              <div>
                <h3 className="mb-1 text-sm font-medium text-muted-foreground">Status</h3>
                <p className="text-sm">
                  {gitInfo.dirty ? (
                    <span className="text-orange-500">Uncommitted changes</span>
                  ) : (
                    <span className="text-green-500">Clean</span>
                  )}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Git information not available</p>
          )}
        </div>
      )}

      {/* Related Experiments */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold text-card-foreground">Related Experiments</h2>
        {project.experiment_count > 0 ? (
          <div>
            <p className="mb-3 text-sm text-muted-foreground">
              This project has {project.experiment_count} experiment{project.experiment_count !== 1 ? 's' : ''}
            </p>
            <button
              onClick={() => navigate('/experiments')}
              className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              View All Experiments
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8">
            <p className="mb-4 text-sm text-muted-foreground">No experiments yet</p>
            <button
              onClick={() => navigate(`/experiments/new?project_id=${id}`)}
              className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" />
              Create Experiment
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
