import type {
  BacktestEvaluateRequest,
  BacktestResult,
  Candle,
  HealthResponse,
  IndicatorSnapshot,
  PaperAccount,
  PaperPerformanceSnapshot,
  PaperProcessRequest,
  PaperStartRequest,
  RiskEvaluateRequest,
  RiskResult,
  StrategyResult,
} from './types'

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...init?.headers,
    },
  })

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Preserve the HTTP status when the server does not return JSON.
    }
    throw new Error(detail)
  }

  return response.json() as Promise<T>
}

function query(path: string, params: Record<string, string | number>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => search.set(key, String(value)))
  return `${path}?${search.toString()}`
}

function jsonRequest(method: 'POST', body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export const tradingGuardApi = {
  getHealth: () => request<HealthResponse>('/health'),

  getMarketCandles: (symbol: string, timeframe: string, limit = 100) =>
    request<Candle[]>(query('/market/candles', { symbol, timeframe, limit })),

  getIndicators: (symbol: string, timeframe: string, limit = 100) =>
    request<IndicatorSnapshot[]>(query('/indicators', { symbol, timeframe, limit })),

  getStrategy: (symbol: string, timeframe: string, limit = 100) =>
    request<StrategyResult[]>(query('/strategy', { symbol, timeframe, limit })),

  evaluateRisk: (payload: RiskEvaluateRequest) =>
    request<RiskResult>('/risk/evaluate', jsonRequest('POST', payload)),

  startPaper: (payload: PaperStartRequest = {}) =>
    request<PaperAccount>('/paper/start', jsonRequest('POST', payload)),

  processPaper: (payload: PaperProcessRequest) =>
    request<PaperAccount>('/paper/process', jsonRequest('POST', payload)),

  getPaperState: () => request<PaperAccount>('/paper/state'),

  getPaperPerformance: () => request<PaperPerformanceSnapshot>('/paper/performance'),

  resetPaper: () => request<PaperAccount>('/paper/reset', jsonRequest('POST', {})),

  evaluateBacktest: (payload: BacktestEvaluateRequest) =>
    request<BacktestResult>('/backtest/evaluate', jsonRequest('POST', payload)),
}

export { API_BASE_URL }
