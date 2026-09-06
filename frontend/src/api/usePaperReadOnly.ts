import { useCallback, useEffect, useState } from 'react'

import { tradingGuardApi } from './client'
import type { PaperAccount, PaperPerformanceSnapshot } from './types'

export interface PaperAccountState {
  account: PaperAccount | null
  performance: PaperPerformanceSnapshot | null
  loading: boolean
  mutating: boolean
  available: boolean
  message: string | null
  start: () => Promise<void>
  reset: () => Promise<void>
  refresh: () => Promise<void>
}

const initialState = {
  account: null as PaperAccount | null,
  performance: null as PaperPerformanceSnapshot | null,
  loading: true,
  mutating: false,
  available: false,
  message: null as string | null,
}

/**
 * Controls the process-local PAPER virtual account only.
 *
 * Start/reset are account lifecycle actions. This hook never processes market
 * events, manufactures RiskContext, or authorizes an entry. Operational paper
 * trading remains fail-closed until the authoritative risk-sizing bridge exists.
 */
export function usePaperReadOnly(): PaperAccountState {
  const [state, setState] = useState(initialState)

  const load = useCallback(async (showLoading = true): Promise<void> => {
    if (showLoading) setState(value => ({ ...value, loading: true, message: null }))
    try {
      const account = await tradingGuardApi.getPaperState()
      let performance: PaperPerformanceSnapshot | null = null
      let message: string | null = null
      try {
        performance = await tradingGuardApi.getPaperPerformance()
      } catch (cause: unknown) {
        message = cause instanceof Error ? cause.message : 'Paper performance is unavailable.'
      }
      setState(value => ({ ...value, account, performance, loading: false, available: true, message }))
    } catch (cause: unknown) {
      setState(value => ({
        ...value,
        account: null,
        performance: null,
        loading: false,
        available: false,
        message: cause instanceof Error ? cause.message : 'Paper session is not available.',
      }))
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const start = useCallback(async (): Promise<void> => {
    setState(value => ({ ...value, mutating: true, message: null }))
    try {
      const account = await tradingGuardApi.startPaper({ config: { initial_capital: 10000.0 } })
      const performance = await tradingGuardApi.getPaperPerformance()
      setState(value => ({ ...value, account, performance, loading: false, mutating: false, available: true, message: null }))
    } catch (cause: unknown) {
      setState(value => ({ ...value, mutating: false, message: cause instanceof Error ? cause.message : 'Unable to start PAPER account.' }))
    }
  }, [])

  const reset = useCallback(async (): Promise<void> => {
    setState(value => ({ ...value, mutating: true, message: null }))
    try {
      const account = await tradingGuardApi.resetPaper()
      const performance = account.active ? await tradingGuardApi.getPaperPerformance() : null
      setState(value => ({ ...value, account, performance, loading: false, mutating: false, available: true, message: null }))
    } catch (cause: unknown) {
      setState(value => ({ ...value, mutating: false, message: cause instanceof Error ? cause.message : 'Unable to reset PAPER account.' }))
    }
  }, [])

  return { ...state, start, reset, refresh: () => load(true) }
}
