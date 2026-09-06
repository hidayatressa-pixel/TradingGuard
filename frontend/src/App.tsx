import { useEffect, useState } from 'react'
import { Activity, RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react'
import { tradingGuardApi, type MarketSource } from './api/client'
import type { Candle, IndicatorSnapshot, StrategyResult } from './api/types'
import './App.css'

type Selection = { source: MarketSource; symbol: string; timeframe: string }
type Data = { candle?: Candle; indicator?: IndicatorSnapshot; strategy?: StrategyResult }
const NA = 'N/A'
const number = (value: number | null | undefined, digits = 2) => value == null ? NA : value.toFixed(digits)

function App() {
  const [selection, setSelection] = useState<Selection>({ source: 'binance', symbol: 'BTCUSDT', timeframe: '1h' })
  const [refreshKey, setRefreshKey] = useState(0)
  const [data, setData] = useState<Data>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    Promise.all([
      tradingGuardApi.getMarketCandles(selection.symbol, selection.timeframe, 100, selection.source),
      tradingGuardApi.getIndicators(selection.symbol, selection.timeframe, 100, selection.source),
      tradingGuardApi.getStrategy(selection.symbol, selection.timeframe, 100, selection.source),
    ])
      .then(([candles, indicators, strategies]) => {
        if (!mounted) return
        setData({ candle: candles.at(-1), indicator: indicators.at(-1), strategy: strategies.at(-1) })
        setError(null)
      })
      .catch((cause: unknown) => {
        if (!mounted) return
        setData({})
        setError(cause instanceof Error ? cause.message : 'Unable to load selected market source.')
      })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [selection, refreshKey])

  const real = selection.source === 'binance'
  return <div className="app-shell min-h-screen text-slate-200">
    <aside className="sidebar fixed inset-y-0 left-0 w-[238px] px-5 py-6">
      <div className="mb-8 flex items-center gap-3"><div className="grid size-9 place-items-center rounded bg-sky-500/15 text-sky-300"><ShieldCheck size={20}/></div><div><div className="font-bold text-white">TradingGuard</div><div className="mono text-[10px] text-slate-500">CONTROL CENTER · v0.8</div></div></div>
      <div className="mono mb-3 text-[9px] uppercase tracking-[.2em] text-slate-600">Operations</div>
      {['Dashboard','Market','Strategy','Risk Guard','Paper Trading','Backtest','Trade Journal','Settings'].map((item, index) => <div key={item} className={`nav-item mb-1 rounded px-3 py-2.5 text-xs ${index === 0 ? 'active' : ''}`}>{item}</div>)}
      <div className="panel-soft absolute bottom-5 left-4 right-4 rounded p-3 text-[10px] text-slate-500">Backend-authoritative read-only market observation. No broker execution.</div>
    </aside>

    <main className="main-area ml-[238px] min-h-screen px-8 py-6">
      <header className="mb-6 border-b border-slate-800 pb-5">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4"><div><div className="mono text-[10px] uppercase tracking-[.18em] text-slate-500">Risk control center</div><h1 className="text-2xl font-bold text-white">Real Market Dashboard</h1></div><div className={`rounded border px-3 py-2 mono text-[10px] ${real ? 'border-sky-500/30 bg-sky-500/10 text-sky-300' : 'border-amber-500/30 bg-amber-500/10 text-amber-300'}`}>● {real ? 'REAL PUBLIC DATA · BINANCE' : 'MOCK DATA'}</div></div>
        <div className="panel-soft flex flex-wrap items-end gap-3 rounded p-4">
          <label className="text-xs"><span className="mono mb-1 block text-[9px] text-slate-500">SOURCE</span><select value={selection.source} onChange={e => setSelection(v => ({...v, source: e.target.value as MarketSource}))} className="rounded border border-slate-700 bg-slate-900 px-3 py-2"><option value="binance">REAL · Binance Public</option><option value="mock">MOCK · Deterministic</option></select></label>
          <label className="text-xs"><span className="mono mb-1 block text-[9px] text-slate-500">SYMBOL</span><select value={selection.symbol} onChange={e => setSelection(v => ({...v, symbol: e.target.value}))} className="rounded border border-slate-700 bg-slate-900 px-3 py-2"><option>BTCUSDT</option><option>ETHUSDT</option><option>BNBUSDT</option></select></label>
          <label className="text-xs"><span className="mono mb-1 block text-[9px] text-slate-500">TIMEFRAME</span><select value={selection.timeframe} onChange={e => setSelection(v => ({...v, timeframe: e.target.value}))} className="rounded border border-slate-700 bg-slate-900 px-3 py-2">{['1m','5m','15m','1h','4h','1d'].map(tf => <option key={tf}>{tf}</option>)}</select></label>
          <button disabled={loading} onClick={() => setRefreshKey(v => v + 1)} className="flex items-center gap-2 rounded border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-300 disabled:opacity-50"><RefreshCw size={14} className={loading ? 'animate-spin' : ''}/>{loading ? 'Loading…' : 'Refresh'}</button>
        </div>
      </header>

      {error && <div className="mb-5 rounded border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-200">Selected source unavailable: {error}. No silent fallback to mock data.</div>}

      <section className="mb-5 grid gap-4 md:grid-cols-3">
        <div className="panel rounded-lg p-5"><div className="mono text-[9px] text-slate-500">LATEST MARKET PRICE</div><div className="mt-3 text-3xl font-bold text-white">{data.candle ? `$${data.candle.close.toLocaleString()}` : NA}</div><div className="mt-2 text-xs text-slate-500">{data.candle?.symbol ?? selection.symbol} · {data.candle?.timeframe ?? selection.timeframe}</div><div className="mt-1 mono text-[9px] text-slate-600">{data.candle ? new Date(data.candle.timestamp).toLocaleString() : NA}</div></div>
        <div className="panel rounded-lg p-5"><div className="mono text-[9px] text-slate-500">MARKET CONDITION · STRATEGY ENGINE</div><div className="mt-3 text-2xl font-bold text-sky-300">{data.strategy?.assessment?.replace(/_/g, ' ') ?? NA}</div><div className="mt-2 text-xs text-slate-500">Score {data.strategy?.score ?? NA} · Normalized {data.strategy?.normalized_score ?? NA}%</div><div className="mt-4 text-[10px] text-slate-500">Market condition ≠ execution permission.</div></div>
        <div className="panel rounded-lg p-5"><div className="mono text-[9px] text-slate-500">EXECUTION PERMISSION · RISK GUARD</div><div className="mt-3 flex items-center gap-2 text-xl font-bold text-slate-500"><ShieldAlert size={20}/>UNAVAILABLE</div><div className="mt-3 text-xs leading-relaxed text-slate-500">Authoritative RiskContext is incomplete. Entry remains fail-closed.</div></div>
      </section>

      <section className="panel mb-5 rounded-lg p-5"><div className="mb-5 flex items-center justify-between"><div><div className="mono text-[9px] text-slate-500">TECHNICAL ENGINE</div><h2 className="mt-1 font-semibold text-white">EMA · RSI · MACD</h2></div><Activity size={18} className="text-sky-400"/></div><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">{[['EMA FAST',data.indicator?.ema_fast],['EMA SLOW',data.indicator?.ema_slow],['RSI',data.indicator?.rsi],['MACD',data.indicator?.macd],['SIGNAL',data.indicator?.macd_signal],['HISTOGRAM',data.indicator?.macd_histogram]].map(([name,value]) => <div className="panel-soft rounded p-3" key={String(name)}><div className="mono text-[9px] text-slate-600">{name}</div><div className="mt-2 font-semibold text-slate-200">{number(value as number | null | undefined, 4)}</div></div>)}</div></section>

      <section className="grid gap-4 lg:grid-cols-2"><div className="panel rounded-lg p-5"><div className="mono text-[9px] text-slate-500">STRATEGY EVIDENCE</div><div className="mt-4 space-y-3">{data.strategy?.evidence?.length ? data.strategy.evidence.map((item, i) => <div className="panel-soft rounded p-3 text-xs" key={`${item.indicator}-${i}`}><div className="flex justify-between"><span className="font-semibold text-slate-300">{item.indicator}</span><span className="mono text-sky-400">{item.contribution > 0 ? '+' : ''}{item.contribution}</span></div><div className="mt-1 text-slate-500">{item.description}</div></div>) : <div className="text-xs text-slate-500">{loading ? 'Loading backend strategy…' : NA}</div>}</div></div><div className="panel rounded-lg p-5"><div className="mono text-[9px] text-slate-500">SAFETY BOUNDARY</div><div className="mt-4 space-y-3 text-xs text-slate-400"><p>Real market data is observation input only.</p><p>Frontend does not calculate strategy, risk, accounting, or trade permission.</p><p>Paper Trading is not automatically started or processed.</p><p>No API key, broker credential, or live order execution is used.</p></div></div></section>
      <footer className="mt-6 border-t border-slate-800 py-5 mono text-[9px] text-slate-600">SOURCE: {real ? 'BINANCE PUBLIC REST MARKET DATA' : 'TRADINGGUARD DETERMINISTIC MOCK'} · READ ONLY · NO BROKER EXECUTION</footer>
    </main>
  </div>
}
export default App
