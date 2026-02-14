import { NavLink, useLocation } from 'react-router-dom'
import {
  Beaker,
  ChevronLeft,
  ChevronRight,
  Cpu,
  FlaskConical,
  Home,
  ListOrdered,
  Moon,
  Play,
  Search,
  Settings,
  SlidersHorizontal,
  Sun,
  Wrench,
} from 'lucide-react'
import { useThemeStore } from '@/stores/themeStore'
import { useSidebarStore } from '@/stores/sidebarStore'
import { useNotifications } from '@/hooks/useNotifications'

interface LayoutProps {
  children: React.ReactNode
}

// ---------------------------------------------------------------------------
// Navigation items
// ---------------------------------------------------------------------------

interface NavItem {
  to: string
  label: string
  icon: React.ReactNode
  badge?: number | null
  /** Match exact path only (default true) */
  end?: boolean
}

function useNavItems(): NavItem[] {
  // TODO: wire to actual running count from store
  const runningCount = 0

  return [
    {
      to: '/',
      label: 'Dashboard',
      icon: <Home className="h-5 w-5" />,
      end: true,
    },
    {
      to: '/experiments',
      label: 'Experiments',
      icon: <FlaskConical className="h-5 w-5" />,
    },
    {
      to: '/running',
      label: 'Running',
      icon: <Play className="h-5 w-5" />,
      badge: runningCount || null,
    },
    {
      to: '/hyperparam',
      label: 'HP Search',
      icon: <SlidersHorizontal className="h-5 w-5" />,
    },
    {
      to: '/queue',
      label: 'Queue',
      icon: <ListOrdered className="h-5 w-5" />,
    },
    {
      to: '/demo/search',
      label: 'Search Demo',
      icon: <Search className="h-5 w-5" />,
    },
    {
      to: '/schemas',
      label: 'Schemas',
      icon: <Wrench className="h-5 w-5" />,
    },
    {
      to: '/settings',
      label: 'Settings',
      icon: <Settings className="h-5 w-5" />,
    },
  ]
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

function Sidebar() {
  const { collapsed, toggle } = useSidebarStore()
  const items = useNavItems()

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-30 flex flex-col border-r border-border bg-card transition-[width] duration-200 ${
        collapsed ? 'w-16' : 'w-56'
      }`}
    >
      {/* Logo area */}
      <div className="flex h-14 items-center gap-2 border-b border-border px-3">
        <Beaker className="h-7 w-7 shrink-0 text-primary" />
        {!collapsed && (
          <span className="truncate text-sm font-semibold text-foreground">
            ML Experiment Hub
          </span>
        )}
      </div>

      {/* Nav links */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              } ${collapsed ? 'justify-center' : ''}`
            }
          >
            {item.icon}
            {!collapsed && (
              <>
                <span className="flex-1 truncate">{item.label}</span>
                {item.badge != null && item.badge > 0 && (
                  <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-bold text-primary-foreground">
                    {item.badge}
                  </span>
                )}
              </>
            )}
            {collapsed && item.badge != null && item.badge > 0 && (
              <span className="absolute right-1 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
                {item.badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggle}
        className="flex h-10 items-center justify-center border-t border-border text-muted-foreground transition-colors hover:text-foreground"
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? (
          <ChevronRight className="h-4 w-4" />
        ) : (
          <ChevronLeft className="h-4 w-4" />
        )}
      </button>
    </aside>
  )
}

// ---------------------------------------------------------------------------
// Top bar
// ---------------------------------------------------------------------------

function TopBar() {
  const { theme, toggle } = useThemeStore()
  const location = useLocation()

  // Derive page title from route
  const title = (() => {
    const path = location.pathname
    if (path === '/') return 'Dashboard'
    if (path === '/experiments') return 'Experiments'
    if (path === '/experiments/new') return 'New Experiment'
    if (path.startsWith('/experiments/') && path.endsWith('/edit'))
      return 'Edit Experiment'
    if (path.startsWith('/experiments/')) return 'Experiment Detail'
    if (path.startsWith('/runs/')) return 'Run Monitor'
    if (path === '/compare' || path.startsWith('/compare?')) return 'Compare'
    if (path === '/running') return 'Running'
    if (path === '/hyperparam') return 'HP Search'
    if (path === '/hyperparam/new') return 'New HP Search'
    if (path.startsWith('/hyperparam/')) return 'HP Search Monitor'
    if (path === '/queue') return 'Experiment Queue'
    if (path === '/demo/search') return 'Search Demo'
    if (path === '/schemas') return 'Schemas'
    if (path === '/settings') return 'Settings'
    return 'ML Experiment Hub'
  })()

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-card/80 px-6 backdrop-blur-sm">
      <h1 className="text-lg font-semibold text-foreground">{title}</h1>

      <div className="flex items-center gap-4">
        {/* GPU status indicator */}
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Cpu className="h-4 w-4" />
          <span>GPU idle</span>
        </div>

        {/* Theme toggle */}
        <button
          onClick={toggle}
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </button>
      </div>
    </header>
  )
}

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

export default function Layout({ children }: LayoutProps) {
  const { collapsed } = useSidebarStore()

  // Connect to global notification WebSocket for browser Notification API
  useNotifications()

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div
        className={`transition-[margin-left] duration-200 ${
          collapsed ? 'ml-16' : 'ml-56'
        }`}
      >
        <TopBar />
        <main className="px-6 py-6">{children}</main>
      </div>
    </div>
  )
}
