import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderGit2, Plus, Tag, Clock, FlaskConical, GitBranch, FolderOpen, Shapes, Upload } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getProjects } from '@/api/projects'
import type { Project, ProjectStatus } from '@/types/project'

// ---------------------------------------------------------------------------
// Status Badge Configuration
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<ProjectStatus, { label: string; classes: string }> = {
  ready: { label: 'Ready', classes: 'bg-green-500/10 text-green-500 border-green-500/20' },
  registered: { label: 'Registered', classes: 'bg-blue-500/10 text-blue-500 border-blue-500/20' },
  cloning: { label: 'Cloning', classes: 'bg-purple-500/10 text-purple-500 border-purple-500/20' },
  scanning: { label: 'Scanning', classes: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20' },
  error: { label: 'Error', classes: 'bg-red-500/10 text-red-500 border-red-500/20' },
}

const SOURCE_TYPE_CONFIG: Record<string, { icon: typeof GitBranch; classes: string }> = {
  github: { icon: GitBranch, classes: 'bg-purple-500/10 text-purple-400 border-purple-500/20' },
  local: { icon: FolderOpen, classes: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  template: { icon: Shapes, classes: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20' },
  upload: { icon: Upload, classes: 'bg-orange-500/10 text-orange-400 border-orange-500/20' },
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ProjectListPage() {
  const navigate = useNavigate()

  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  // ── Fetch projects ─────────────────────────────────────────────
  useEffect(() => {
    const fetchProjects = async () => {
      setLoading(true)
      try {
        const data = await getProjects()
        setProjects(data.projects || [])
        setTotal(data.total || 0)
      } catch {
        // Silently handle fetch errors
      } finally {
        setLoading(false)
      }
    }

    fetchProjects()
  }, [])

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Projects</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {total} project{total !== 1 ? 's' : ''} registered
          </p>
        </div>
        <button
          onClick={() => navigate('/projects/new')}
          className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Register Project
        </button>
      </div>

      {/* Loading State */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="animate-pulse rounded-lg border border-border bg-card p-6"
            >
              <div className="mb-4 h-6 w-3/4 rounded bg-muted"></div>
              <div className="mb-2 h-4 w-full rounded bg-muted"></div>
              <div className="mb-4 h-4 w-2/3 rounded bg-muted"></div>
              <div className="flex gap-2">
                <div className="h-6 w-16 rounded bg-muted"></div>
                <div className="h-6 w-16 rounded bg-muted"></div>
              </div>
            </div>
          ))}
        </div>
      ) : projects.length === 0 ? (
        /* Empty State */
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card py-16 text-center">
          <FolderGit2 className="mb-4 h-12 w-12 text-muted-foreground/50" />
          <h3 className="mb-2 text-lg font-semibold text-foreground">
            No projects yet
          </h3>
          <p className="mb-6 text-sm text-muted-foreground">
            Register your first ML project to start tracking experiments
          </p>
          <button
            onClick={() => navigate('/projects/new')}
            className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            Register your first project
          </button>
        </div>
      ) : (
        /* Project Grid */
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => {
            const statusCfg = STATUS_CONFIG[project.status] || STATUS_CONFIG.registered
            const sourceTypeCfg = project.source_type ? SOURCE_TYPE_CONFIG[project.source_type] : null
            const truncatedPath =
              project.path.length > 50
                ? '...' + project.path.slice(-47)
                : project.path
            const truncatedGitUrl = project.git_url && project.git_url.length > 40
              ? project.git_url.slice(0, 37) + '...'
              : project.git_url

            return (
              <div
                key={project.id}
                onClick={() => navigate(`/projects/${project.id}`)}
                className="group cursor-pointer rounded-lg border border-border bg-card p-6 transition-all hover:border-primary/50 hover:shadow-md"
              >
                {/* Header */}
                <div className="mb-4 flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="mb-1 text-lg font-semibold text-foreground group-hover:text-primary">
                      {project.name}
                    </h3>
                    <p
                      className="text-xs text-muted-foreground"
                      title={project.path}
                    >
                      {truncatedPath}
                    </p>
                    {project.git_url && (
                      <p
                        className="mt-1 text-xs text-muted-foreground/70"
                        title={project.git_url}
                      >
                        {truncatedGitUrl}
                      </p>
                    )}
                  </div>
                  <FolderGit2 className="h-5 w-5 text-muted-foreground/50 group-hover:text-primary/50" />
                </div>

                {/* Badges */}
                <div className="mb-4 flex flex-wrap gap-2">
                  {/* Status */}
                  <span
                    className={cn(
                      'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
                      statusCfg.classes,
                    )}
                  >
                    {statusCfg.label}
                  </span>

                  {/* Source Type */}
                  {sourceTypeCfg && (
                    <span
                      className={cn(
                        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
                        sourceTypeCfg.classes,
                      )}
                    >
                      <sourceTypeCfg.icon className="h-3 w-3" />
                    </span>
                  )}

                  {/* Project Type */}
                  <span className="inline-flex items-center rounded-md border border-border bg-background px-2 py-0.5 text-xs font-medium text-muted-foreground">
                    {project.project_type}
                  </span>

                  {/* Python Env */}
                  {project.python_env && (
                    <span className="inline-flex items-center rounded-md border border-border bg-background px-2 py-0.5 text-xs font-medium text-muted-foreground">
                      {project.python_env}
                    </span>
                  )}
                </div>

                {/* Metadata */}
                <div className="space-y-2 border-t border-border pt-4">
                  {/* Experiment Count */}
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <FlaskConical className="h-3.5 w-3.5" />
                    <span>
                      {project.experiment_count} experiment
                      {project.experiment_count !== 1 ? 's' : ''}
                    </span>
                  </div>

                  {/* Tags */}
                  {project.tags.length > 0 && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Tag className="h-3.5 w-3.5" />
                      <div className="flex flex-wrap gap-1">
                        {project.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="rounded bg-secondary px-1.5 py-0.5 text-secondary-foreground"
                          >
                            {tag}
                          </span>
                        ))}
                        {project.tags.length > 3 && (
                          <span className="text-xs">
                            +{project.tags.length - 3}
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Created At */}
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock className="h-3.5 w-3.5" />
                    <span>{formatDate(project.created_at)}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHr / 24)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24) return `${diffHr}h ago`
  if (diffDay < 7) return `${diffDay}d ago`

  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
