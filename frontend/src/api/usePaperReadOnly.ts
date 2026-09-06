import { useEffect, useState } from 'react'

import { tradingGuardApi } from './client'
import type { PaperAccount, PaperPerformanceSnapshot } from './types'

export interface PaperReadOnlyState {
  account: PaperAccount | null
  performance: PaperPerformanceSnapshot | null
  loading: boolean
  available: boolean
  message: string | null
}

const initialState: PaperReadOnlyState = {
  account: null,
  performance: null,
  loading: true,
  available: false,
  message: null,
}

/**
 * Reads the process-local V0.7 paper account without mutating it.
 *
 * This hook intentionally never starts, resets, or processes a paper session.
 * A missing session is an unavailable state, not a zero-valued account.
 */
export function usePaperReadOnly(): PaperReadOnlyState {
  const [state, setState] = useState<PaperReadOnlyState>(initialState)

  useEffect(() => {
    let mounted = true

    async function load(): Promise<void> {
      try {
        const account = await tradingGuardApi.getPaperState()
        if (!mounted) return

        // Performance belongs to an existing authoritative account. Keep its
        // failure independent so account state can still be shown truthfully.
        try {
          const performance = await tradingGuardApi.getPaperPerformance()
          if (!mounted) return
          setState({ account, performance, loading: false, available: true, message: null })
        } catch (cause: unknown) {
          if (!mounted) return
          setState({
            account,
            performance: null,
            loading: false,
            available: true,
            message: cause instanceof Error ? cause.message : 'Paper performance is unavailable.',
          })
        }
      } catch (cause: unknown) {
        if (!mounted) return
        setState({
          account: null,
          performance: null,
          loading: false,
          available: false,
          message: cause instanceof Error ? cause.message : 'Paper session is not available.',
        })
      }
    }

    void load()

    return () => {
      mounted = false
    }
  }, [])

  return state
}
