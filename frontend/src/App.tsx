import { useEffect, useState, type ReactNode } from 'react'
import { Activity, BarChart3, BookOpen, Database, RefreshCw, Settings, ShieldAlert, ShieldCheck, TestTube2, WalletCards } from 'lucide-react'
import { tradingGuardApi, type MarketSource } from './api/client'
import { useBacktest } from './api/useBacktest'
import { usePaperReadOnly } from './api/usePaperReadOnly'
import type { Candle, IndicatorSnapshot, StrategyResult } from './api/types'
import { BacktestView, DashboardView, MarketView, PaperTradingView, RiskGuardView, SettingsView, StrategyView, TradeJournalView, type Selection } from './components/DashboardViews'
import './App.css'

type View = 'Dashboard' | 'Market' | 'Strategy' | 'Risk Guard' | 'Paper Trading' | 'Backtest' | 'Trade Journal' | 'Settings'
type Data = { candles: Candle[]; indicators: IndicatorSnapshot[]; strategies: StrategyResult[] }

const nav: Array<{ name: View; icon: typeof Activity }> = [
  { name: 'Dashboard', icon: Activity }, { name: 'Market', icon: BarChart3 }, { name: 'Strategy', icon: Database },
  { name: 'Risk Guard', icon: ShieldAlert }, { name: 'Paper Trading', icon: WalletCards }, { name: 'Backtest', icon: TestTube2 },
  { name: 'Trade Journal', icon: BookOpen }, { name: 'Settings', icon: Settings },
]

function App() {
  const [view, setView] = useState<View>('Dashboard')
  const [selection, setSelection] = useState<Selection>({ source: 'binance', symbol: 'BTCUSDT', timeframe: '1h' })
  const [refreshKey, setRefreshKey] = useState(0)
  const [data, setData] = useState<Data>({ candles: [], indicators: [], strategies: [] })
  const [loadedRequest, setLoadedRequest] = useState('')
  const [error, setError] = useState<string | null>(null)
  const paper = usePaperReadOnly()
  const backtest = useBacktest()
  const requestKey = `${selection.source}:${selection.symbol}:${selection.timeframe}:${refreshKey}`
  const loading = loadedRequest !== requestKey

  useEffect(() => {
    let mounted = true
    Promise.all([
      tradingGuardApi.getMarketCandles(selection.symbol, selection.timeframe, 100, selection.source),
      tradingGuardApi.getIndicators(selection.symbol, selection.timeframe, 100, selection.source),
      tradingGuardApi.getStrategy(selection.symbol, selection.timeframe, 100, selection.source),
    ]).then(([candles, indicators, strategies]) => {
      if (!mounted) return
      setData({ candles, indicators, strategies })
      setError(null)
      setLoadedRequest(requestKey)
    }).catch((cause: unknown) => {
      if (!mounted) return
      setData({ candles: [], indicators: [], strategies: [] })
      setError(cause instanceof Error ? cause.message : 'Unable to load selected market source.')
      setLoadedRequest(requestKey)
    })
    return () => { mounted = false }
  }, [selection, refreshKey, requestKey])

  const candle = data.candles.at(-1)
  const indicator = data.indicators.at(-1)
  const strategy = data.strategies.at(-1)
  const real = selection.source === 'binance'

  const controls = <div className="panel-soft flex flex-wrap items-end gap-3 rounded p-4">
    <label className="text-xs"><span className="mono mb-1 block text-[9px] text-slate-500">SOURCE</span><select value={selection.source} onChange={event => setSelection(value => ({ ...value, source: event.target.value as MarketSource }))} className="rounded border border-slate-700 bg-slate-900 px-3 py-2"><option value="binance">REAL · Binance Public</option><option value="mock">MOCK · Deterministic</option></select></label>
    <label className="text-xs"><span className="mono mb-1 block text-[9px] text-slate-500">SYMBOL</span><select value={selection.symbol} onChange={event => setSelection(value => ({ ...value, symbol: event.target.value }))} className="rounded border border-slate-700 bg-slate-900 px-3 py-2"><option>BTCUSDT</option><option>ETHUSDT</option><option>BNBUSDT</option></select></label>
    <label className="text-xs"><span className="mono mb-1 block text-[9px] text-slate-500">TIMEFRAME</span><select value={selection.timeframe} onChange={event => setSelection(value => ({ ...value, timeframe: event.target.value }))} className="rounded border border-slate-700 bg-slate-900 px-3 py-2">{['1m','5m','15m','1h','4h','1d'].map(timeframe => <option key={timeframe}>{timeframe}</option>)}</select></label>
    <button disabled={loading} onClick={() => setRefreshKey(value => value + 1)} className="flex items-center gap-2 rounded border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-300 disabled:opacity-50"><RefreshCw size={14} className={loading ? 'animate-spin' : ''}/>{loading ? 'Loading…' : 'Refresh'}</button>
  </div>

  const content: Record<View, ReactNode> = {
    Dashboard: <DashboardView selection={selection} candle={candle} indicator={indicator} strategy={strategy} loading={loading}/>,
    Market: <MarketView candles={data.candles} symbol={selection.symbol}/>,
    Strategy: <StrategyView strategy={strategy} loading={loading}/>,
    'Risk Guard': <RiskGuardView strategy={strategy}/>,
    'Paper Trading': <PaperTradingView paper={paper}/>,
    Backtest: <BacktestView backtest={backtest} candles={data.candles} strategies={data.strategies} loading={loading}/>,
    'Trade Journal': <TradeJournalView paper={paper}/>,
    Settings: <SettingsView selection={selection}/>,
  }

  return <div className="app-shell min-h-screen text-slate-200">
    <aside className="sidebar fixed inset-y-0 left-0 w-[238px] px-4 py-6">
      <div className="mb-8 flex items-center gap-3"><div className="grid size-9 place-items-center rounded bg-sky-500/15 text-sky-300"><ShieldCheck size={20}/></div><div><div className="font-bold text-white">TradingGuard</div><div className="mono text-[10px] text-slate-500">CONTROL CENTER · v0.8</div></div></div>
      <div className="mono mb-3 text-[9px] uppercase tracking-[.2em] text-slate-600">Operations</div>
      {nav.map(item => { const Icon = item.icon; return <button key={item.name} onClick={() => setView(item.name)} className={`nav-item mb-1 flex w-full items-center gap-2 rounded px-3 py-2.5 text-left text-xs ${view === item.name ? 'active' : ''}`}><Icon size={14}/>{item.name}</button> })}
      <div className="panel-soft absolute bottom-5 left-4 right-4 rounded p-3 text-[10px] text-slate-500">Backend-authoritative control center. No broker execution.</div>
    </aside>
    <main className="main-area ml-[238px] min-h-screen px-8 py-6">
      <header className="mb-6 border-b border-slate-800 pb-5"><div className="mb-5 flex flex-wrap items-center justify-between gap-4"><div><div className="mono text-[10px] uppercase tracking-[.18em] text-slate-500">Risk control center</div><h1 className="text-2xl font-bold text-white">{view === 'Dashboard' ? 'Real Market Dashboard' : view}</h1></div><div className={`rounded border px-3 py-2 mono text-[10px] ${real ? 'border-sky-500/30 bg-sky-500/10 text-sky-300' : 'border-amber-500/30 bg-amber-500/10 text-amber-300'}`}>● {real ? 'REAL PUBLIC DATA · BINANCE' : 'MOCK DATA'}</div></div>{controls}</header>
      {error && <div className="mb-5 rounded border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-200">Selected source unavailable: {error}. No silent fallback to mock data.</div>}
      {content[view]}
      <footer className="mt-6 border-t border-slate-800 py-5 mono text-[9px] text-slate-600">SOURCE: {real ? 'BINANCE PUBLIC REST MARKET DATA' : 'TRADINGGUARD DETERMINISTIC MOCK'} · READ ONLY MARKET INPUT · NO BROKER EXECUTION</footer>
    </main>
  </div>
}

export default App
