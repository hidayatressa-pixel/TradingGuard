import { useEffect, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Activity, BarChart3, BookOpen, ChevronRight, CircleHelp, Gauge, LineChart, Settings, ShieldAlert, ShieldCheck, SlidersHorizontal, Wallet } from 'lucide-react'
import { tradingGuardApi } from './api/client'
import { usePaperReadOnly } from './api/usePaperReadOnly'
import type { Candle, IndicatorSnapshot, StrategyResult } from './api/types'
import './App.css'

interface DashboardData { candle?: Candle; indicator?: IndicatorSnapshot; strategy?: StrategyResult }
function useDashboardData() {
  const [data, setData] = useState<DashboardData>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let mounted = true
    Promise.all([tradingGuardApi.getMarketCandles('BTCUSD', '1h'), tradingGuardApi.getIndicators('BTCUSD', '1h'), tradingGuardApi.getStrategy('BTCUSD', '1h')])
      .then(([candles, indicators, strategies]) => { if (!mounted) return; setData({ candle: candles.at(-1), indicator: indicators.at(-1), strategy: strategies.at(-1) }); setError(null) })
      .catch((cause: unknown) => { if (mounted) setError(cause instanceof Error ? cause.message : 'Unable to load backend data.') })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [])
  return { ...data, loading, error }
}

type NavItem = { label: string; icon: LucideIcon; future?: boolean }
const navItems: NavItem[] = [
  { label: 'Dashboard', icon: Gauge }, { label: 'Market', icon: LineChart, future: true }, { label: 'Strategy', icon: SlidersHorizontal, future: true },
  { label: 'Risk Guard', icon: ShieldCheck }, { label: 'Paper Trading', icon: Wallet }, { label: 'Backtest', icon: BarChart3, future: true },
  { label: 'Trade Journal', icon: BookOpen }, { label: 'Settings', icon: Settings, future: true },
]
const NA = 'N/A'
const money = (v: number | null | undefined) => v == null ? NA : `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const num = (v: number | null | undefined, d = 2) => v == null ? NA : v.toFixed(d)
const pct = (v: number | null | undefined) => v == null ? NA : `${v.toFixed(2)}%`
const time = (v: string | null | undefined) => v ? new Date(v).toLocaleString() : NA
const label = (v: string | null | undefined) => v ? v.replace(/_/g, ' ') : NA
function SectionHeader({ eyebrow, title, action }: { eyebrow: string; title: string; action?: string }) {
  return <div className="mb-5 flex items-start justify-between"><div><p className="mono mb-1 text-[10px] uppercase tracking-[.18em] text-slate-500">{eyebrow}</p><h2 className="text-[15px] font-semibold text-slate-100">{title}</h2></div>{action && <span className="mono rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-500">{action}</span>}</div>
}

function App() {
  const { candle, indicator, strategy, loading, error } = useDashboardData()
  const paper = usePaperReadOnly()
  const account = paper.account
  const performance = paper.performance
  const position = account?.open_position
  const strategyWidth = strategy ? `${strategy.normalized_score}%` : '0%'
  const backendStatus = loading ? 'AWAITING BACKEND' : error ? 'BACKEND UNAVAILABLE' : 'BACKEND DATA'
  const paperStatus = paper.loading ? 'LOADING' : paper.available ? (account?.active ? 'ACTIVE' : 'INACTIVE') : 'NOT STARTED'
  return <div className="app-shell text-slate-200">
    <aside className="sidebar fixed inset-y-0 left-0 z-20 flex w-[238px] flex-col px-3 py-5">
      <div className="mb-9 flex items-center gap-3 px-3"><div className="grid size-9 place-items-center rounded bg-sky-500/15 text-sky-300"><ShieldCheck size={20}/></div><div className="brand-copy"><div className="text-sm font-bold tracking-tight text-slate-100">TradingGuard</div><div className="mono text-[10px] text-slate-500">CONTROL CENTER <span className="text-sky-400">v0.8</span></div></div></div>
      <div className="nav-group-label mono mb-2 px-3 text-[9px] uppercase tracking-[.2em] text-slate-600">Operations</div>
      <nav className="space-y-1">{navItems.map(({ label: item, icon: Icon, future }) => <div className={`nav-item flex items-center gap-3 rounded px-3 py-2.5 text-xs ${item === 'Dashboard' ? 'active' : ''}`} key={item}><Icon size={16}/><span className="sidebar-label flex-1">{item}</span>{future && <span className="future-badge mono text-[8px] uppercase text-slate-600">future</span>}</div>)}</nav>
      <div className="mt-auto panel-soft rounded p-3"><div className="mb-2 flex items-center gap-2"><span className={`status-dot size-2 rounded-full ${error ? 'bg-amber-400' : 'bg-sky-400'}`}/><span className="mono text-[9px] uppercase tracking-wider text-sky-300">{backendStatus}</span></div><p className="sidebar-label mb-0 text-[11px] leading-relaxed text-slate-500">Read-only dashboard. Backend remains authoritative.</p></div>
    </aside>
    <main className="main-area ml-[238px] min-h-screen px-7 py-5 lg:px-9">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-5"><div><div className="mb-1 flex items-center gap-2"><span className="mono text-[10px] uppercase tracking-[.18em] text-slate-500">Risk control center</span><ChevronRight size={12} className="text-slate-700"/><span className="mono text-[10px] text-sky-400">BACKEND DATA</span></div><h1 className="text-2xl font-bold tracking-tight text-white">System dashboard</h1></div><div className="flex flex-wrap items-center gap-3"><div className="panel-soft flex items-center gap-3 rounded px-3 py-2"><div><div className="mono text-[9px] text-slate-500">INSTRUMENT</div><div className="text-sm font-semibold">{candle?.symbol ?? NA} <span className="text-slate-500">· {candle?.timeframe ?? NA}</span></div></div><Activity size={16} className="text-sky-400"/></div><div className="flex items-center gap-2 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2"><span className="text-amber-400">●</span><span className="mono text-[10px] font-semibold tracking-wide text-amber-300">BACKEND MOCK MARKET DATA</span></div></div></header>
      {error && <div className="mb-5 rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">Market/strategy backend unavailable: {error}</div>}
      {paper.message && <div className="mb-5 rounded border border-slate-700 bg-slate-800/40 p-3 text-xs text-slate-400">Paper read-only status: {paper.message}</div>}
      <section className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Market data" title="Latest price" action={candle?.symbol ?? NA}/><div className="metric-number text-3xl font-bold text-white">{money(candle?.close)}</div><div className="mt-2 mono text-[10px] text-slate-600">{time(candle?.timestamp)}</div></div>
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Strategy logic" title="Market condition" action={strategy ? `${strategy.score > 0 ? '+' : ''}${strategy.score}` : NA}/><div className="flex items-end justify-between"><div className="text-xl font-bold text-sky-300">{label(strategy?.assessment)}</div><span className="mono text-xs text-slate-500">{strategy?.normalized_score ?? NA}%</span></div><div className="gauge mt-4 overflow-hidden rounded"><div className="gauge-fill h-full rounded" style={{ width: strategyWidth }}/></div><p className="mt-3 text-[10px] text-slate-500">Market condition is not execution permission.</p></div>
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Risk filter" title="Execution permission" action="V0.5"/><div className="flex items-center gap-2 text-slate-500"><ShieldAlert size={19}/><span className="text-xl font-bold">UNAVAILABLE</span></div><p className="mt-3 text-xs leading-relaxed text-slate-400">Awaiting authoritative risk context. New entry remains fail-closed.</p></div>
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Paper account" title="Portfolio state" action="VIRTUAL"/><div className="flex items-end justify-between"><div><div className="mono text-[10px] text-slate-500">SESSION</div><div className="mt-1 text-lg font-bold text-slate-100">{paperStatus}</div></div><Wallet size={21} className="text-sky-400"/></div><div className="mt-4 border-t border-slate-800 pt-3"><div className="mono text-[9px] text-slate-500">REALIZED EQUITY</div><div className="text-xl font-semibold text-white">{money(account?.realized_equity)}</div></div></div>
      </section>
      <section className="mb-5 grid gap-4 xl:grid-cols-2">
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Backend indicators" title="Technical snapshot" action={indicator ? 'AUTHORITATIVE' : NA}/><div className="grid grid-cols-2 gap-4 text-xs md:grid-cols-3">{[['EMA FAST', indicator?.ema_fast], ['EMA SLOW', indicator?.ema_slow], ['RSI', indicator?.rsi], ['MACD', indicator?.macd], ['SIGNAL', indicator?.macd_signal], ['HISTOGRAM', indicator?.macd_histogram]].map(([name, value]) => <div key={String(name)}><div className="mono text-[9px] text-slate-600">{name}</div><div className="mt-1 text-slate-200">{num(value as number | null | undefined, 4)}</div></div>)}</div></div>
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Authoritative risk" title="Control gate" action="AWAITING CONTEXT"/><div className="space-y-4">{['Risk decision', 'Risk per trade', 'Daily loss', 'Drawdown', 'Exposure'].map(item => <div className="flex items-center gap-3" key={item}><ShieldAlert size={14} className="text-slate-600"/><div className="flex flex-1 justify-between text-xs"><span className="text-slate-400">{item}</span><span className="mono text-[10px] text-slate-500">{NA}</span></div></div>)}</div><p className="mt-5 text-[10px] leading-relaxed text-slate-500">Unknown risk facts are never converted to zero. Allocation is never interpreted as risk per trade.</p></div>
      </section>
      <section className="mb-5 grid gap-4 xl:grid-cols-[.9fr_1.6fr]">
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Account pipeline" title="Open position" action={position ? 'OPEN' : account ? 'FLAT' : NA}/><div className="mb-5 flex items-center justify-between border-b border-slate-800 pb-4"><div><div className="mono text-[9px] text-slate-600">POSITION</div><div className="mt-1 text-2xl font-bold text-white">{position?.symbol ?? (account ? 'FLAT' : NA)}</div></div><div className="text-right"><div className="mono text-[9px] text-slate-600">CASH</div><div className="text-sm font-semibold text-slate-300">{money(account?.cash)}</div></div></div><div className="grid grid-cols-2 gap-y-5 text-xs"><div><div className="mono text-[9px] text-slate-600">ENTRY PRICE</div><div className="mt-1">{money(position?.entry_price)}</div></div><div><div className="mono text-[9px] text-slate-600">QUANTITY</div><div className="mt-1">{num(position?.quantity, 8)}</div></div><div><div className="mono text-[9px] text-slate-600">ENTRY NOTIONAL</div><div className="mt-1">{money(position?.entry_notional)}</div></div><div><div className="mono text-[9px] text-slate-600">LAST EVENT</div><div className="mt-1">{time(account?.last_event_timestamp)}</div></div></div><div className="mt-6 rounded border border-sky-500/15 bg-sky-500/5 p-3 text-[10px] leading-relaxed text-slate-500">Read-only backend state. This dashboard does not start or process paper trades.</div></div>
        <div className="panel rounded-lg p-5"><div className="mb-4 flex flex-wrap items-start justify-between gap-3"><SectionHeader eyebrow="Audit trail" title="Trade journal" action={account ? `${account.closed_trades.length} CLOSED` : NA}/><div className="flex items-center gap-2 rounded border border-slate-800 px-2 py-1 text-[10px] text-slate-500"><BookOpen size={12}/> Backend records only</div></div><div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left"><thead className="mono text-[9px] uppercase tracking-wider text-slate-600"><tr><th className="pb-3">Exit</th><th className="pb-3">Symbol</th><th className="pb-3 text-right">Net P/L</th><th className="pb-3 text-right">Return</th><th className="pb-3 text-right">Equity</th></tr></thead><tbody>{account?.closed_trades.length ? account.closed_trades.slice().reverse().slice(0, 8).map(trade => <tr className="table-row border-t border-slate-800/80 text-xs" key={`${trade.entry_timestamp}-${trade.exit_timestamp}`}><td className="py-3 text-slate-500">{time(trade.exit_timestamp)}</td><td className="py-3 text-slate-300">{trade.symbol}</td><td className="py-3 text-right">{money(trade.net_pnl)}</td><td className="py-3 text-right">{pct(trade.return_pct)}</td><td className="py-3 text-right">{money(trade.equity_after)}</td></tr>) : <tr><td className="py-4 text-slate-500" colSpan={5}>{account ? 'No closed paper trades.' : 'Paper session unavailable / not started.'}</td></tr>}</tbody></table></div></div>
      </section>
      <section className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Paper performance" title="Realized return"/><div className="text-2xl font-bold text-white">{pct(performance?.realized_return_pct)}</div><p className="mt-2 text-[10px] text-slate-500">Backend realized-only metric.</p></div>
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Paper performance" title="Win rate"/><div className="text-2xl font-bold text-white">{pct(performance?.win_rate_pct)}</div><p className="mt-2 text-[10px] text-slate-500">Closed trades: {performance?.total_closed_trades ?? NA}</p></div>
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Paper performance" title="Profit factor"/><div className="text-2xl font-bold text-white">{num(performance?.profit_factor)}</div><p className="mt-2 text-[10px] text-slate-500">No frontend recomputation.</p></div>
        <div className="panel rounded-lg p-5"><SectionHeader eyebrow="Backtest" title="Evaluation" action="NOT RUN"/><div className="text-2xl font-bold text-slate-500">{NA}</div><p className="mt-2 text-[10px] text-slate-500">No fabricated backtest result. Requires an explicit authoritative run.</p></div>
      </section>
      <section className="panel rounded-lg p-5"><SectionHeader eyebrow="Backend strategy" title="Evidence monitor" action={strategy ? `${strategy.evidence.length} RULES` : NA}/><div className="overflow-x-auto"><table className="w-full min-w-[520px] text-left"><thead className="mono text-[9px] uppercase tracking-wider text-slate-600"><tr><th className="pb-3">Indicator</th><th className="pb-3">Observation</th><th className="pb-3 text-right">Contribution</th></tr></thead><tbody>{strategy?.evidence.length ? strategy.evidence.map(item => <tr className="table-row border-t border-slate-800/80 text-xs" key={`${item.indicator}-${item.condition}`}><td className="py-3 font-medium text-slate-300">{item.indicator}</td><td className="py-3 text-slate-500">{item.description}</td><td className="py-3 text-right font-semibold">{item.contribution > 0 ? '+' : ''}{item.contribution}</td></tr>) : <tr><td className="py-4 text-slate-500" colSpan={3}>{NA}</td></tr>}</tbody></table></div><div className="mt-4 flex gap-2 border-t border-slate-800 pt-3 text-[10px] text-slate-500"><CircleHelp size={13}/> Evidence is displayed as returned by the Strategy Engine.</div></section>
    </main>
  </div>
}
export default App
