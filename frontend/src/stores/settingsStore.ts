import { create } from 'zustand'

type TimezonePreference = 'local' | 'utc'

interface SettingsState {
  timezone: TimezonePreference
  setTimezone: (tz: TimezonePreference) => void
}

const stored = (typeof localStorage !== 'undefined'
  ? localStorage.getItem('ml-hub-timezone')
  : null) as TimezonePreference | null

const initial: TimezonePreference = stored ?? 'local'

export const useSettingsStore = create<SettingsState>((set) => ({
  timezone: initial,
  setTimezone: (tz) => {
    localStorage.setItem('ml-hub-timezone', tz)
    set({ timezone: tz })
  },
}))
