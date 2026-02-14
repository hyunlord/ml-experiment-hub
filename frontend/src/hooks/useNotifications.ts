import { useEffect, useRef, useCallback } from 'react'
import { useWebSocket } from './useWebSocket'

/**
 * Hook that connects to the global /ws/notifications endpoint
 * and shows browser Notification API popups for training events.
 *
 * Must be called once at the app level (e.g. in Layout).
 */
export function useNotifications() {
  const permissionRef = useRef<NotificationPermission>('default')

  // Request notification permission on mount
  useEffect(() => {
    if ('Notification' in window) {
      permissionRef.current = Notification.permission
      if (Notification.permission === 'default') {
        Notification.requestPermission().then((perm) => {
          permissionRef.current = perm
        })
      }
    }
  }, [])

  const showNotification = useCallback(
    (title: string, body: string, tag?: string) => {
      if (
        'Notification' in window &&
        permissionRef.current === 'granted'
      ) {
        new Notification(title, {
          body,
          tag: tag || 'ml-hub',
          icon: '/favicon.ico',
        })
      }
    },
    []
  )

  useWebSocket('ws://localhost:8000/ws/notifications', {
    handlers: {
      run_started: (data: unknown) => {
        const d = data as {
          experiment_name?: string
          run_id?: number
          message?: string
        }
        showNotification(
          'Training Started',
          d.message || `${d.experiment_name} (Run #${d.run_id})`,
          `run-start-${d.run_id}`
        )
      },
      run_completed: (data: unknown) => {
        const d = data as {
          experiment_name?: string
          run_id?: number
          message?: string
          duration?: string
        }
        const body = d.duration
          ? `${d.message || d.experiment_name} (${d.duration})`
          : d.message || `${d.experiment_name} completed`
        showNotification(
          'Training Completed',
          body,
          `run-done-${d.run_id}`
        )
      },
      run_failed: (data: unknown) => {
        const d = data as {
          experiment_name?: string
          run_id?: number
          message?: string
        }
        showNotification(
          'Training Failed',
          d.message || `${d.experiment_name} failed`,
          `run-fail-${d.run_id}`
        )
      },
    },
  })
}
