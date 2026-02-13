import { create } from 'zustand'

type Theme = 'dark' | 'light'

interface ThemeState {
  theme: Theme
  toggle: () => void
  set: (theme: Theme) => void
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  localStorage.setItem('theme', theme)
}

const stored = (typeof localStorage !== 'undefined'
  ? localStorage.getItem('theme')
  : null) as Theme | null

const initial: Theme = stored ?? 'dark'

// Apply on load
if (typeof document !== 'undefined') {
  applyTheme(initial)
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: initial,
  toggle: () =>
    set((s) => {
      const next = s.theme === 'dark' ? 'light' : 'dark'
      applyTheme(next)
      return { theme: next }
    }),
  set: (theme) => {
    applyTheme(theme)
    set({ theme })
  },
}))
