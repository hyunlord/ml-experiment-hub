import { useCallback, useEffect, useRef, useState } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected'

/** Map message `type` field to its handler. Unmatched types go to `onMessage`. */
export type MessageHandlers = Record<string, (data: unknown) => void>

export interface UseWebSocketOptions {
  /** Initial reconnect delay in ms (default 1000). Doubles on each attempt. */
  reconnectDelay?: number
  /** Maximum reconnect delay in ms (default 30000). */
  maxReconnectDelay?: number
  /** Maximum reconnect attempts before giving up (default 10). 0 = infinite. */
  maxReconnectAttempts?: number
  /** Keepalive ping interval in ms (default 25000). 0 = disabled. */
  pingInterval?: number
  /** Per-type message handlers. Key = `type` field value. */
  handlers?: MessageHandlers
  /** Catch-all handler for messages without a matching type handler. */
  onMessage?: (data: unknown) => void
  /** Called when connection opens. */
  onOpen?: () => void
  /** Called when connection closes (includes whether it will reconnect). */
  onClose?: (willReconnect: boolean) => void
  /** Called on connection error. */
  onError?: (event: Event) => void
}

export interface UseWebSocketReturn {
  /** Current connection status. */
  status: ConnectionStatus
  /** Shorthand: status === 'connected'. */
  isConnected: boolean
  /** Send a string or object (auto-serialized to JSON). */
  send: (data: string | Record<string, unknown>) => void
  /** Manually close the connection (disables reconnect). */
  close: () => void
  /** Manually trigger a reconnect attempt. */
  reconnect: () => void
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Generic WebSocket hook with exponential backoff reconnection
 * and per-message-type handler dispatch.
 *
 * @example
 * ```ts
 * const { status, send } = useWebSocket(wsUrl, {
 *   handlers: {
 *     metric: (data) => metricsStore.ingest(data as MetricMessage),
 *     system_stats: (data) => systemStore.ingest(data as SystemMessage),
 *     log: (data) => addLog(data as LogMessage),
 *   },
 * })
 * ```
 */
export function useWebSocket(
  url: string | null,
  options: UseWebSocketOptions = {},
): UseWebSocketReturn {
  const {
    reconnectDelay = 1000,
    maxReconnectDelay = 30000,
    maxReconnectAttempts = 10,
    pingInterval = 25000,
    handlers,
    onMessage,
    onOpen,
    onClose,
    onError,
  } = options

  const [status, setStatus] = useState<ConnectionStatus>('disconnected')

  const wsRef = useRef<WebSocket | null>(null)
  const attemptsRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const manualCloseRef = useRef(false)

  // Keep latest callbacks in refs to avoid re-connecting on handler changes
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage
  const onOpenRef = useRef(onOpen)
  onOpenRef.current = onOpen
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError

  const connect = useCallback(() => {
    if (!url) return

    // Clean up previous
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onmessage = null
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      if (wsRef.current.readyState < WebSocket.CLOSING) {
        wsRef.current.close()
      }
    }

    setStatus('connecting')
    const ws = new WebSocket(url)

    ws.onopen = () => {
      setStatus('connected')
      attemptsRef.current = 0
      onOpenRef.current?.()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        const type = (data as Record<string, unknown>)?.type as string | undefined

        // Skip keepalive/pong frames
        if (type === 'keepalive' || type === 'pong') return

        // Dispatch to typed handler if available
        if (type && handlersRef.current?.[type]) {
          handlersRef.current[type](data)
          return
        }

        // Fallback catch-all
        onMessageRef.current?.(data)
      } catch {
        // Non-JSON message; pass raw string to catch-all
        onMessageRef.current?.(event.data)
      }
    }

    ws.onerror = (event) => {
      onErrorRef.current?.(event)
    }

    ws.onclose = () => {
      wsRef.current = null
      setStatus('disconnected')

      if (manualCloseRef.current) {
        manualCloseRef.current = false
        onCloseRef.current?.(false)
        return
      }

      const canReconnect =
        maxReconnectAttempts === 0 || attemptsRef.current < maxReconnectAttempts

      onCloseRef.current?.(canReconnect)

      if (canReconnect) {
        // Exponential backoff with jitter
        const delay = Math.min(
          reconnectDelay * Math.pow(2, attemptsRef.current),
          maxReconnectDelay,
        )
        const jitter = delay * 0.1 * Math.random()
        attemptsRef.current++

        reconnectTimerRef.current = setTimeout(connect, delay + jitter)
      }
    }

    wsRef.current = ws
  }, [url, reconnectDelay, maxReconnectDelay, maxReconnectAttempts])

  // Auto-connect when url changes
  useEffect(() => {
    if (!url) {
      setStatus('disconnected')
      return
    }

    manualCloseRef.current = false
    attemptsRef.current = 0
    connect()

    // Keepalive ping
    let pingTimer: ReturnType<typeof setInterval> | undefined
    if (pingInterval > 0) {
      pingTimer = setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send('ping')
        }
      }, pingInterval)
    }

    return () => {
      if (pingTimer) clearInterval(pingTimer)
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      manualCloseRef.current = true
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [url, connect, pingInterval])

  const send = useCallback((data: string | Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  const close = useCallback(() => {
    manualCloseRef.current = true
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
    wsRef.current?.close()
  }, [])

  const reconnect = useCallback(() => {
    manualCloseRef.current = false
    attemptsRef.current = 0
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
    connect()
  }, [connect])

  return {
    status,
    isConnected: status === 'connected',
    send,
    close,
    reconnect,
  }
}
