import { useCallback, useEffect, useRef, useState } from 'react'

type Channel = 'metrics' | 'system' | 'logs'

interface UseRunWebSocketReturn<T = unknown> {
  data: T[]
  lastMessage: T | null
  isConnected: boolean
  send: (msg: string) => void
  clear: () => void
}

/**
 * Channel-aware WebSocket hook for run monitoring.
 * Connects to /ws/runs/{runId}/{channel} and accumulates messages.
 */
export function useRunWebSocket<T = unknown>(
  runId: number | string | null,
  channel: Channel,
): UseRunWebSocketReturn<T> {
  const [data, setData] = useState<T[]>([])
  const [lastMessage, setLastMessage] = useState<T | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>()
  const attemptsRef = useRef(0)

  useEffect(() => {
    if (!runId) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/runs/${runId}/${channel}`

    const connect = () => {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        setIsConnected(true)
        attemptsRef.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as T
          // Skip keepalive/pong
          const type = (msg as Record<string, unknown>)?.type
          if (type === 'keepalive' || type === 'pong') return

          setData((prev) => [...prev, msg])
          setLastMessage(msg)
        } catch {
          // ignore parse errors
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        wsRef.current = null
        if (attemptsRef.current < 10) {
          attemptsRef.current++
          reconnectRef.current = setTimeout(connect, 3000)
        }
      }

      ws.onerror = () => ws.close()
      wsRef.current = ws
    }

    connect()

    // Ping keepalive every 25s
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 25000)

    return () => {
      clearInterval(pingInterval)
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [runId, channel])

  const send = useCallback((msg: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(msg)
    }
  }, [])

  const clear = useCallback(() => {
    setData([])
    setLastMessage(null)
  }, [])

  return { data, lastMessage, isConnected, send, clear }
}
