import { useState } from 'react'
import { tradingGuardApi } from './client'
import type { AutoPaperEntryRequest, AutoPaperEntryResult } from './types'

export function useAutoPaper() {
  const [result, setResult] = useState<AutoPaperEntryResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const evaluate = async (payload: AutoPaperEntryRequest) => {
    setRunning(true)
    setError(null)
    try {
      const next = await tradingGuardApi.autoPaperEntry(payload)
      setResult(next)
      return next
    } catch (cause: unknown) {
      const message = cause instanceof Error ? cause.message : 'Evaluasi Auto Paper gagal.'
      setError(message)
      throw cause
    } finally {
      setRunning(false)
    }
  }

  const clear = () => {
    setResult(null)
    setError(null)
  }

  return { result, running, error, evaluate, clear }
}
