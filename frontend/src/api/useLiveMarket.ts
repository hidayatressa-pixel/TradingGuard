import { useEffect, useState } from 'react'
import type { MarketSource } from './client'

type LiveMarketState = {
  price: number | null
  eventTime: number | null
  connected: boolean
  error: string | null
}

const initialState: LiveMarketState = { price: null, eventTime: null, connected: false, error: null }
const STREAM_HOSTS = ['wss://data-stream.binance.vision/ws', 'wss://stream.binance.com:9443/ws', 'wss://stream.binance.com:443/ws']
const STALE_AFTER_MS = 15_000
const MAX_BACKOFF_MS = 30_000

export function useLiveMarket(source: MarketSource, symbol: string): LiveMarketState {
  const [state, setState] = useState<LiveMarketState>(initialState)

  useEffect(() => {
    if (source !== 'binance') return

    let active = true
    let reconnectTimer: number | undefined
    let watchdogTimer: number | undefined
    let socket: WebSocket | null = null
    let hostIndex = 0
    let attempts = 0
    let lastMessageAt = 0

    const clearTimers = () => {
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      if (watchdogTimer !== undefined) window.clearInterval(watchdogTimer)
    }

    const scheduleReconnect = () => {
      if (!active || reconnectTimer !== undefined) return
      const delay = Math.min(1000 * 2 ** Math.min(attempts, 5), MAX_BACKOFF_MS)
      attempts += 1
      hostIndex = (hostIndex + 1) % STREAM_HOSTS.length
      setState(value => ({ ...value, connected: false, error: `Live stream reconnecting in ${Math.ceil(delay / 1000)}s.` }))
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = undefined
        connect()
      }, delay)
    }

    const connect = () => {
      if (!active) return
      socket?.close()
      const stream = `${symbol.toLowerCase()}@trade`
      socket = new WebSocket(`${STREAM_HOSTS[hostIndex]}/${stream}`)

      socket.onopen = () => {
        if (!active) return
        lastMessageAt = Date.now()
        setState(value => ({ ...value, price: null, eventTime: null, connected: true, error: null }))
      }
      socket.onmessage = event => {
        if (!active) return
        try {
          const payload = JSON.parse(String(event.data)) as { p?: string; E?: number }
          const price = Number(payload.p)
          if (Number.isFinite(price) && price > 0) {
            lastMessageAt = Date.now()
            attempts = 0
            setState({ price, eventTime: typeof payload.E === 'number' ? payload.E : Date.now(), connected: true, error: null })
          }
        } catch {
          setState(value => ({ ...value, error: 'Invalid live market message.' }))
        }
      }
      socket.onerror = () => {
        if (!active) return
        setState(value => ({ ...value, connected: false, error: 'Live market stream unavailable.' }))
        socket?.close()
      }
      socket.onclose = () => {
        if (!active) return
        setState(value => ({ ...value, connected: false }))
        scheduleReconnect()
      }
    }

    watchdogTimer = window.setInterval(() => {
      if (!active || !socket) return
      if (socket.readyState === WebSocket.OPEN && lastMessageAt > 0 && Date.now() - lastMessageAt > STALE_AFTER_MS) {
        setState(value => ({ ...value, connected: false, error: 'Live market stream stale; reconnecting.' }))
        socket.close()
      }
    }, 5000)

    connect()
    return () => {
      active = false
      clearTimers()
      socket?.close()
    }
  }, [source, symbol])

  if (source !== 'binance') return initialState
  return state
}
