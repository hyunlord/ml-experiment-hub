import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(relativeTime)
dayjs.extend(utc)
dayjs.extend(timezone)

export function getTimezonePreference(): 'local' | 'utc' {
  const stored = typeof localStorage !== 'undefined'
    ? localStorage.getItem('ml-hub-timezone')
    : null
  return (stored as 'local' | 'utc') ?? 'local'
}

export function formatRelativeTime(utcDateString: string): string {
  const parsed = dayjs.utc(utcDateString)
  return parsed.fromNow()
}

export function formatAbsoluteTime(utcDateString: string): string {
  const parsed = dayjs.utc(utcDateString)
  const pref = getTimezonePreference()

  if (pref === 'utc') {
    return parsed.format('YYYY-MM-DD HH:mm') + ' UTC'
  } else {
    return parsed.local().format('YYYY-MM-DD HH:mm')
  }
}

export function formatChartTime(utcDateString: string): string {
  const parsed = dayjs.utc(utcDateString)
  const pref = getTimezonePreference()

  if (pref === 'utc') {
    return parsed.format('HH:mm')
  } else {
    return parsed.local().format('HH:mm')
  }
}

export function getDetectedTimezone(): string {
  const tz = dayjs.tz.guess()
  const offset = getTimezoneOffset()
  return `${tz} (${offset})`
}

export function getTimezoneOffset(): string {
  const offsetMinutes = dayjs().utcOffset()
  const hours = Math.floor(Math.abs(offsetMinutes) / 60)
  const minutes = Math.abs(offsetMinutes) % 60
  const sign = offsetMinutes >= 0 ? '+' : '-'

  if (minutes === 0) {
    return `UTC${sign}${hours}`
  } else {
    return `UTC${sign}${hours}:${minutes.toString().padStart(2, '0')}`
  }
}
