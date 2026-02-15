import { create } from 'zustand'
import type { Server } from '@/api/servers'
import { listServers } from '@/api/servers'

interface ServerState {
  servers: Server[]
  activeServerId: number | null
  loading: boolean

  /** Fetch server list from backend. */
  fetchServers: () => Promise<void>

  /** Set active server by ID. Persists to localStorage. */
  setActive: (id: number | null) => void

  /** Get the currently active server object. */
  getActive: () => Server | null
}

const storedId =
  typeof localStorage !== 'undefined'
    ? localStorage.getItem('ml-hub-active-server')
    : null

export const useServerStore = create<ServerState>((set, get) => ({
  servers: [],
  activeServerId: storedId ? Number(storedId) : null,
  loading: false,

  fetchServers: async () => {
    set({ loading: true })
    try {
      const servers = await listServers()
      const state = get()
      let activeId = state.activeServerId

      // If no active server set, pick the default or local one
      if (activeId === null || !servers.find((s) => s.id === activeId)) {
        const def = servers.find((s) => s.is_default) ?? servers.find((s) => s.is_local) ?? servers[0]
        activeId = def?.id ?? null
      }

      set({ servers, activeServerId: activeId, loading: false })
      if (activeId !== null) {
        localStorage.setItem('ml-hub-active-server', String(activeId))
      }
    } catch {
      set({ loading: false })
    }
  },

  setActive: (id) => {
    set({ activeServerId: id })
    if (id !== null) {
      localStorage.setItem('ml-hub-active-server', String(id))
    } else {
      localStorage.removeItem('ml-hub-active-server')
    }
  },

  getActive: () => {
    const { servers, activeServerId } = get()
    return servers.find((s) => s.id === activeServerId) ?? null
  },
}))
