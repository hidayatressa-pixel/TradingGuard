import { useEffect, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  BarChart3,
  BookOpen,
  ChevronRight,
  CircleHelp,
  Gauge,
  LineChart,
  Settings,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Wallet,
} from 'lucide-react'
import { tradingGuardApi } from './api/client'
import type { Candle, IndicatorSnapshot, StrategyResult } from './api/types'
import './App.css'

interface DashboardData {
  candle: Candle | undefined
  indicator: IndicatorSnapshot | undefined
  strategy: StrategyResult | undefined
}

const emptyDashboard: DashboardData = {
  candle: undefined,
  indicator: undefined,
  strategy: undefined,
}

function useDashboardData() {
  const [data, setData] = useState<DashboardData>(emptyDashboard)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    Promise.all([
      tradingGuardApi.getMarketCandles('BTCUSD', '1h'),
      tradingGuardApi.getIndicators('BTCUSD', '1h'),
      tradingGuardApi.getStrategy('BTCUSD', '1h'),
    ])
      .then(([candles, indicators, strategies]) => {
        if (!mounted) return
        setData({
          candle: candles[candles.length - 1],
          indicator: indicators[indicators.length - 1],
          strategy: strategies[strategies.length - 1],
        })
        setError(null)
      })
      .catch((cause: unknown) => {
        if (!mounted) return
        setError(cause instanceof Error ? cause.message : 'Unable to load backend data.')
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [])

  return { ...data, loading, error }
}

type NavItem = { label: string; icon: LucideIcon; future?: boolean }

const navItems: NavItem[] = [
  { label: 'Dashboard', icon: Gauge },
  { label: 'Market', icon: LineChart, future: true },
  { label: 'Strategy', icon: SlidersHorizontal, future: true },
  { label: 'Risk Guard', icon: ShieldCheck },
  { label: 'Paper Trading', icon: Wallet },
  { label: 'Backtest', icon: BarChart3, future: true },
  { label: 'Trade Journal', icon: BookOpen },
  { label: 'Settings', icon: Settings, future: true },
]

const unavailable = 'N/A'

const money = (value: number | null | undefined) =>
  value === null || value === undefined
    ? unavailable
    : `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

const number = (value: number | null | undefined, digits = 2) =>
  value === null || value === undefined ? unavailable : value.toFixed(digits)

const time = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : unavailable

const label = (value: string | null | undefined) => (value ? value.replace(/_/g, ' ') : unavailable)

function SectionHeader({ eyebrow, title, action }: { eyebrow: string; title: string; action?: string }) {
  return (
    <div className="mb-5 flex items-start justify-between">
      <div>
        <p className="mono mb-1 text-[10px] uppercase tracking-[.18em] text-slate-500">{eyebrow}</p>
        <h2 className="text-[15px] font-semibold text-slate-100">{title}</h2>
      </div>
      {action && <span className="mono rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-500">{action}</span>}
    </div>
  )
}

function App() {
  const { candle, indicator, strategy, loading, error } = useDashboardData()
  const statusLabel = loading ? 'AWAITING BACKEND' : error ? 'BACKEND UNAVAILABLE' : 'BACKEND DATA'
  const strategyWidth = strategy ? `${strategy.normalized_score}%` : '0%'

  return (
    <div className="app-shell text-slate-200">
      <aside className="sidebar fixed inset-y-0 left-0 z-20 flex w-[238px] flex-col px-3 py-5">
        <div className="mb-9 flex items-center gap-3 px-3">
          <div className="grid size-9 place-items-center rounded bg-sky-500/15 text-sky-300"><ShieldCheck size={20} /></div>
          <div className="brand-copy">
            <div className="text-sm font-bold tracking-tight text-slate-100">TradingGuard</div>
            <div className="mono text-[10px] text-slate-500">CONTROL CENTER <span className="text-sky-400">v0.8</span></div>
          </div>
        </div>
        <div className="nav-group-label mono mb-2 px-3 text-[9px] uppercase tracking-[.2em] text-slate-600">Operations</div>
        <nav className="space-y-1">
          {navItems.map(({ label: itemLabel, icon: Icon, future }) => (
            <div className={`nav-item flex items-center gap-3 rounded px-3 py-2.5 text-xs ${itemLabel === 'Dashboard' ? 'active' : ''}`} key={itemLabel}>
              <Icon size={16} />
              <span className="sidebar-label flex-1">{itemLabel}</span>
              {future && <span className="future-badge mono text-[8px] uppercase text-slate-600">future</span>}
            </div>
          ))}
        </nav>
        <div className="mt-auto panel-soft rounded p-3">
          <div className="mb-2 flex items-center gap-2">
            <span className={`status-dot size-2 rounded-full ${error ? 'bg-amber-400' : 'bg-sky-400'}`} />
            <span className="mono text-[9px] uppercase tracking-wider text-sky-300">{statusLabel}</span>
          </div>
          <p className="sidebar-label mb-0 text-[11px] leading-relaxed text-slate-500">Read-only frontend. Backend is the source of truth.</p>
        </div>
      </aside>

      <main className="main-area ml-[238px] min-h-screen px-7 py-5 lg:px-9">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <span className="mono text-[10px] uppercase tracking-[.18em] text-slate-500">Risk control center</span>
              <ChevronRight size={12} className="text-slate-700" />
              <span className="mono text-[10px] text-sky-400">BACKEND DATA</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">System dashboard</h1>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="panel-soft flex items-center gap-3 rounded px-3 py-2">
              <div>
                <div className="mono text-[9px] text-slate-500">INSTRUMENT</div>
                <div className="text-sm font-semibold">{candle?.symbol ?? unavailable} <span className="text-slate-500">· {candle?.timeframe ?? unavailable}</span></div>
              </div>
              <Activity size={16} className="text-sky-400" />
            </div>
            <div className="flex items-center gap-2 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2">
              <span className="text-amber-400">●</span>
              <span className="mono text-[10px] font-semibold tracking-wide text-amber-300">BACKEND MOCK DATA</span>
            </div>
          </div>
        </header>

        <div className="mb-5 flex flex-wrap items-center justify-between gap-2">
          <div className="mono text-[10px] uppercase tracking-[.16em] text-slate-500">READ-ONLY BACKEND DASHBOARD <span className="pulse-line ml-2 text-sky-400">●</span></div>
          <div className="mono text-[10px] text-slate-600">LAST EVENT {time(candle?.timestamp)}</div>
        </div>

        {error && <div className="mb-5 rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">Backend data unavailable: {error}</div>}

        <section className="mb-5 grid gap-4 xl:grid-cols-4 md:grid-cols-2">
          <div className="panel relative overflow-hidden rounded-lg p-5">
            <div className="grid-lines absolute inset-x-0 bottom-0 h-20" />
            <SectionHeader eyebrow="Market data" title="Latest price" action={candle?.symbol ?? unavailable} />
            <div className="relative">
              <div className="metric-number text-3xl font-bold text-white">{money(candle?.close)}</div>
              <div className="mt-2 flex items-center gap-2"><span className="text-xs text-slate-500">{unavailable}</span><span className="mono text-[10px] text-slate-600">{time(candle?.timestamp)} UTC</span></div>
            </div>
          </div>
          <div className="panel rounded-lg p-5">
            <SectionHeader eyebrow="Strategy logic" title="Signal assessment" action={strategy ? `${strategy.score > 0 ? '+' : ''}${strategy.score}` : unavailable} />
            <div className="flex items-end justify-between"><div className="text-xl font-bold text-sky-300">{label(strategy?.assessment)}</div><span className="mono text-xs text-slate-500">{strategy?.normalized_score ?? unavailable}%</span></div>
            <div className="gauge mt-4 overflow-hidden rounded"><div className="gauge-fill h-full rounded" style={{ width: strategyWidth }} /></div>
            <p className="mt-3 text-[10px] leading-relaxed text-slate-500">Strategy assessment is provided by the backend.</p>
          </div>
          <div className="panel rounded-lg p-5">
            <SectionHeader eyebrow="Risk filter" title="Authorization gate" action="V0.5" />
            <div className="flex items-center gap-2 text-slate-500"><ShieldAlert size={19} /><span className="text-xl font-bold tracking-tight">UNAVAILABLE</span></div>
            <p className="mt-3 text-xs leading-relaxed text-slate-400">Awaiting authoritative risk context.</p>
          </div>
          <div className="panel rounded-lg p-5">
            <SectionHeader eyebrow="Paper account" title="Portfolio state" action="VIRTUAL" />
            <div className="flex items-end justify-between"><div><div className="mono text-[10px] text-slate-500">POSITION STATE</div><div className="mt-1 text-lg font-bold text-slate-100">{unavailable}</div></div><Wallet size={21} className="text-sky-400" /></div>
            <div className="mt-4 border-t border-slate-800 pt-3"><div className="mono text-[9px] text-slate-500">REALIZED EQUITY</div><div className="text-xl font-semibold text-white">{unavailable}</div></div>
          </div>
        </section>

        <section className="mb-5 grid gap-4 xl:grid-cols-2">
          <div className="panel rounded-lg p-5">
            <SectionHeader eyebrow="Backend strategy" title="Evidence monitor" action={strategy ? `${strategy.evidence.length} RULES` : unavailable} />
            <div className="overflow-x-auto">
              <table className="w-full min-w-[440px] text-left">
                <thead className="mono text-[9px] uppercase tracking-wider text-slate-600"><tr><th className="pb-3 font-medium">Indicator</th><th className="pb-3 font-medium">Observation</th><th className="pb-3 text-right font-medium">Contribution</th></tr></thead>
                <tbody>{strategy?.evidence.map((item) => <tr className="table-row border-t border-slate-800/80 text-xs" key={`${item.indicator}-${item.condition}`}><td className="py-3 font-medium text-slate-300">{item.indicator}</td><td className="py-3 text-slate-500">{item.description}</td><td className={`py-3 text-right font-semibold ${item.contribution > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{item.contribution > 0 ? '+' : ''}{item.contribution}</td></tr>) ?? <tr><td className="py-3 text-slate-500" colSpan={3}>{unavailable}</td></tr>}</tbody>
              </table>
            </div>
            <div className="mt-4 flex gap-2 border-t border-slate-800 pt-3 text-[10px] leading-relaxed text-slate-500"><CircleHelp size={13} className="mt-0.5 shrink-0 text-slate-600" /> Strategy evidence is displayed exactly as returned by the backend.</div>
          </div>
          <div className="panel rounded-lg p-5">
            <SectionHeader eyebrow="Authoritative risk" title="Control gate" action="AWAITING CONTEXT" />
            <div className="space-y-4">{['Risk decision', 'Drawdown limit', 'Open positions', 'Trading structure'].map((item) => <div className="flex items-center gap-3" key={item}><div className="grid size-7 place-items-center rounded-full bg-slate-400/10 text-slate-500"><ShieldAlert size={14} /></div><div className="flex-1"><div className="flex justify-between gap-3 text-xs"><span className="text-slate-400">{item}</span><span className="mono text-[10px] text-slate-500">{unavailable}</span></div><div className="mt-2 h-px bg-slate-800" /></div></div>)}</div>
            <p className="mt-5 text-[10px] leading-relaxed text-slate-500">Unavailable / Awaiting authoritative risk context.</p>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[.9fr_1.6fr]">
          <div className="panel rounded-lg p-5">
            <SectionHeader eyebrow="Account pipeline" title="Open position" action={unavailable} />
            <div className="mb-5 flex items-center justify-between border-b border-slate-800 pb-4"><div><div className="mono text-[9px] text-slate-600">POSITION</div><div className="mt-1 text-2xl font-bold text-white">{unavailable}</div></div><div className="text-right text-sm font-semibold text-slate-500">{unavailable}<div className="mono text-[9px] text-slate-600">P/L</div></div></div>
            <div className="grid grid-cols-2 gap-y-5 text-xs">{['Entry price', 'Current mark', 'Open quantity', 'Notional size'].map((item) => <div key={item}><div className="mono text-[9px] text-slate-600">{item.toUpperCase()}</div><div className="mt-1 text-slate-200">{unavailable}</div></div>)}</div>
            <div className="mt-6 rounded border border-sky-500/15 bg-sky-500/5 p-3 text-[10px] leading-relaxed text-slate-500">Unavailable / Awaiting authoritative paper account state.</div>
          </div>
          <div className="panel rounded-lg p-5">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3"><SectionHeader eyebrow="Audit trail" title="Trade journal" action={unavailable} /><div className="flex items-center gap-2 rounded border border-slate-800 px-2 py-1 text-[10px] text-slate-500"><BookOpen size={12} /> Backend state unavailable</div></div>
            <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left"><thead className="mono text-[9px] uppercase tracking-wider text-slate-600"><tr>{['Time', 'Type', 'Price', 'Quantity', 'Fees', 'Net P/L', 'Equity'].map((header) => <th className="border-b border-slate-800 pb-3 font-medium" key={header}>{header}</th>)}</tr></thead><tbody><tr><td className="py-3 text-slate-500" colSpan={7}>{unavailable} / Awaiting authoritative paper account state.</td></tr></tbody></table></div>
            <div className="mt-5 grid grid-cols-2 gap-3 border-t border-slate-800 pt-4 md:grid-cols-4">{['Net profit', 'Return', 'Win rate', 'Profit factor'].map((item) => <div key={item}><div className="mono text-[9px] uppercase text-slate-600">{item}</div><div className="mt-1 text-sm font-semibold text-slate-200">{unavailable}</div></div>)}</div>
            <p className="mt-4 text-[10px] leading-relaxed text-slate-600">Paper execution and performance are not started or calculated by this frontend.</p>
          </div>
        </section>

        <div className="mt-4 text-[10px] text-slate-600">Indicator snapshot: EMA fast {number(indicator?.ema_fast)} · EMA slow {number(indicator?.ema_slow)} · RSI {number(indicator?.rsi, 1)} · MACD histogram {number(indicator?.macd_histogram)}</div>
      </main>
    </div>
  )
}

export default App
