import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderGit2, Plus, Clock, FlaskConical, GitBranch, FolderOpen, Shapes, Upload, Link2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getProjects } from '@/api/projects'
import type { Project, ProjectStatus } from '@/types/project'
import { formatRelativeTime, formatAbsoluteTime } from '@/utils/time'

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

            return (
              <div
                key={project.id}
                onClick={() => navigate(`/projects/${project.id}`)}
                className="group cursor-pointer rounded-lg border border-border bg-card p-6 transition-all hover:border-primary/50 hover:shadow-md"
              >
                {/* Title with icon */}
                <div className="mb-3 flex items-center gap-2">
                  <FolderGit2 className="h-5 w-5 flex-shrink-0 text-muted-foreground/50 group-hover:text-primary/50" />
                  <h3 className="truncate text-lg font-semibold text-foreground group-hover:text-primary">
                    {project.name}
                  </h3>
                </div>

                {/* Description */}
                {project.description && (
                  <p className="mb-3 line-clamp-2 text-sm text-muted-foreground">
                    {project.description}
                  </p>
                )}

                {/* Git URL */}
                {project.git_url && (
                  <div className="mb-2 flex items-center gap-1.5">
                    <Link2 className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                    <a
                      href={project.git_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="truncate text-xs text-muted-foreground/70 hover:text-primary hover:underline"
                      title={project.git_url}
                    >
                      {shortenUrl(project.git_url)}
                    </a>
                  </div>
                )}

                {/* Path */}
                <div className="mb-4 flex items-center gap-1.5">
                  <FolderOpen className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                  <p className="truncate text-xs text-muted-foreground" title={project.path}>
                    {project.path}
                  </p>
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

                {/* Footer */}
                <div className="flex items-center gap-2 border-t border-border pt-4 text-xs text-muted-foreground">
                  <FlaskConical className="h-3.5 w-3.5" />
                  <span>
                    {project.experiment_count} experiment
                    {project.experiment_count !== 1 ? 's' : ''}
                  </span>
                  <span>·</span>
                  <Clock className="h-3.5 w-3.5" />
                  <span title={formatAbsoluteTime(project.created_at)}>{formatRelativeTime(project.created_at)}</span>
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

function shortenUrl(url: string): string {
  return url.replace(/^https?:\/\//, '').replace(/\.git$/, '')
}
