import { useState } from 'react'

import { tradingGuardApi } from './client'
import type { BacktestResult, Candle, StrategyResult } from './types'

interface BacktestState {
  result: BacktestResult | null
  running: boolean
  error: string | null
}

function assertAligned(candles: Candle[], strategies: StrategyResult[]): void {
  if (candles.length === 0 || strategies.length === 0) {
    throw new Error('Backtest requires backend candle and strategy sequences.')
  }
  if (candles.length !== strategies.length) {
    throw new Error('Backend candle and strategy sequences are not aligned.')
  }

  for (let index = 0; index < candles.length; index += 1) {
    const candle = candles[index]
    const strategy = strategies[index]
    if (
      candle.timestamp !== strategy.timestamp ||
      candle.symbol !== strategy.symbol ||
      candle.timeframe !== strategy.timeframe
    ) {
      throw new Error(`Backend sequence alignment failed at index ${index}.`)
    }
  }
}

/**
 * Explicit controller for V0.6 backend backtesting.
 * React validates identity/alignment only; all trading/performance calculations
 * remain authoritative in the FastAPI backtest engine.
 */
export function useBacktest() {
  const [state, setState] = useState<BacktestState>({ result: null, running: false, error: null })

  async function run(candles: Candle[], strategies: StrategyResult[]): Promise<void> {
    setState(previous => ({ ...previous, running: true, error: null }))
    try {
      assertAligned(candles, strategies)
      const result = await tradingGuardApi.evaluateBacktest({ candles, strategy_results: strategies })
      setState({ result, running: false, error: null })
    } catch (cause: unknown) {
      setState({
        result: null,
        running: false,
        error: cause instanceof Error ? cause.message : 'Backtest evaluation failed.',
      })
    }
  }

  return { ...state, run }
}
