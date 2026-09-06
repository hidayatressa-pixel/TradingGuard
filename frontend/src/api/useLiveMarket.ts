import { useEffect, useState } from 'react'
import type { MarketSource } from './client'

type LiveMarketState = {
  price: number | null
  eventTime: number | null
  connected: boolean
  error: string | null
}

const initialState: LiveMarketState = { price: null, eventTime: null, connected: false, error: null }

export function useLiveMarket(source: MarketSource, symbol: string): LiveMarketState {
  const [state, setState] = useState<LiveMarketState>(initialState)

  useEffect(() => {
    if (source !== 'binance') return

    let active = true
    let reconnectTimer: number | undefined
    let socket: WebSocket | null = null

    const connect = () => {
      if (!active) return
      socket = new WebSocket(`wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@trade`)

      socket.onopen = () => {
        if (active) setState({ price: null, eventTime: null, connected: true, error: null })
      }
      socket.onmessage = event => {
        if (!active) return
        try {
          const payload = JSON.parse(String(event.data)) as { p?: string; E?: number }
          const price = Number(payload.p)
          if (Number.isFinite(price) && price > 0) {
            setState({ price, eventTime: typeof payload.E === 'number' ? payload.E : Date.now(), connected: true, error: null })
          }
        } catch {
          setState(value => ({ ...value, error: 'Invalid live market message.' }))
        }
      }
      socket.onerror = () => {
        if (active) setState(value => ({ ...value, connected: false, error: 'Live market stream unavailable.' }))
      }
      socket.onclose = () => {
        if (!active) return
        setState(value => ({ ...value, connected: false }))
        reconnectTimer = window.setTimeout(connect, 3000)
      }
    }

    connect()
    return () => {
      active = false
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [source, symbol])

  if (source !== 'binance') return initialState
  return state
}
