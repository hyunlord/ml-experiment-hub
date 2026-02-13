import { create } from 'zustand'

interface SidebarState {
  collapsed: boolean
  toggle: () => void
}

const stored =
  typeof localStorage !== 'undefined'
    ? localStorage.getItem('sidebar-collapsed')
    : null

export const useSidebarStore = create<SidebarState>((set) => ({
  collapsed: stored === 'true',
  toggle: () =>
    set((s) => {
      const next = !s.collapsed
      localStorage.setItem('sidebar-collapsed', String(next))
      return { collapsed: next }
    }),
}))
