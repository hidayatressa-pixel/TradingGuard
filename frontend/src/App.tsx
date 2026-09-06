import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Activity, BarChart3, BookOpen, Database, Pause, Play, RefreshCw, Settings, ShieldAlert, ShieldCheck, TestTube2, WalletCards } from 'lucide-react'
import { tradingGuardApi, type MarketSource } from './api/client'
import { useBacktest } from './api/useBacktest'
import { useLiveMarket } from './api/useLiveMarket'
import { usePaperReadOnly } from './api/usePaperReadOnly'
import type { AutoPaperCycleResult, Candle, IndicatorSnapshot, StrategyResult } from './api/types'
import { AutoPaperControl } from './components/AutoPaperControl'
import { BacktestView, MarketView, SettingsView, StrategyView, TradeJournalView, type Selection } from './components/DashboardViews'
import { DashboardIndonesia, PaperTradingIndonesia, RiskGuardIndonesia } from './components/LocalizedCoreViews'
import { MarketChart } from './components/MarketChart'
import { PositionRuntimePanel } from './components/PositionRuntimePanel'
import { StrategyTransitionHistory } from './components/StrategyTransitionHistory'
import './App.css'

type View='Dashboard'|'Market'|'Strategy'|'Risk Guard'|'Paper Trading'|'Backtest'|'Trade Journal'|'Settings'
type Data={candles:Candle[];indicators:IndicatorSnapshot[];strategies:StrategyResult[]}
type ChartRange='1H'|'4H'|'1D'|'1W'|'1M'
const MARKET_REFRESH_SECONDS=5
const rangeTimeframe:Record<ChartRange,string>={'1H':'1m','4H':'5m','1D':'15m','1W':'1h','1M':'4h'}
const nav:Array<{name:View;label:string;icon:typeof Activity}>=[{name:'Dashboard',label:'Dashboard',icon:Activity},{name:'Market',label:'Pasar',icon:BarChart3},{name:'Strategy',label:'Strategi',icon:Database},{name:'Risk Guard',label:'Risk Guard',icon:ShieldAlert},{name:'Paper Trading',label:'Paper Trading',icon:WalletCards},{name:'Backtest',label:'Backtest',icon:TestTube2},{name:'Trade Journal',label:'Jurnal Trade',icon:BookOpen},{name:'Settings',label:'Pengaturan',icon:Settings}]
const title:Record<View,string>={Dashboard:'Dashboard Pasar Real',Market:'Pasar',Strategy:'Strategi','Risk Guard':'Risk Guard','Paper Trading':'Paper Trading',Backtest:'Backtest','Trade Journal':'Jurnal Trade',Settings:'Pengaturan'}

function App(){
 const [view,setView]=useState<View>('Dashboard'),[source,setSource]=useState<MarketSource>('binance'),[symbol,setSymbol]=useState('BTCUSDT'),[chartRange,setChartRange]=useState<ChartRange>('1D')
 const timeframe=rangeTimeframe[chartRange],selection:Selection={source,symbol,timeframe}
 const [refreshKey,setRefreshKey]=useState(0),[autoRefresh,setAutoRefresh]=useState(true),[data,setData]=useState<Data>({candles:[],indicators:[],strategies:[]}),[loadedRequest,setLoadedRequest]=useState(''),[error,setError]=useState<string|null>(null)
 const [autoCycle,setAutoCycle]=useState<AutoPaperCycleResult|null>(null),[autoCycleError,setAutoCycleError]=useState<string|null>(null)
 const autoCycleInFlight=useRef(false)
 const paper=usePaperReadOnly(),backtest=useBacktest(),live=useLiveMarket(source,symbol),requestKey=`${source}:${symbol}:${timeframe}:${refreshKey}`,loading=loadedRequest!==requestKey
 const paperActive=Boolean(paper.account?.active),paperRefresh=paper.refresh

 useEffect(()=>{let mounted=true;Promise.all([tradingGuardApi.getMarketCandles(symbol,timeframe,100,source),tradingGuardApi.getIndicators(symbol,timeframe,100,source),tradingGuardApi.getStrategy(symbol,timeframe,100,source)]).then(([candles,indicators,strategies])=>{if(!mounted)return;setData({candles,indicators,strategies});setError(null);setLoadedRequest(requestKey)}).catch((cause:unknown)=>{if(!mounted)return;setData({candles:[],indicators:[],strategies:[]});setError(cause instanceof Error?cause.message:'Sumber data pasar yang dipilih tidak dapat dimuat.');setLoadedRequest(requestKey)});return()=>{mounted=false}},[source,symbol,timeframe,refreshKey,requestKey])
 useEffect(()=>{if(!autoRefresh)return;const timer=window.setInterval(()=>setRefreshKey(value=>value+1),MARKET_REFRESH_SECONDS*1000);return()=>window.clearInterval(timer)},[autoRefresh])

 // Binance REST includes the currently-forming candle as the last item. Execution decisions
 // deliberately exclude it, so every decision-facing screen must display the same completed
 // candle (-2) rather than the forming candle (-1). Live/current price remains display-only.
 const completedCandle=data.candles.at(-2)
 const completedIndicator=data.indicators.at(-2),completedStrategy=data.strategies.at(-2)
 const real=source==='binance'
 const operational=paper.account?.open_position??paper.account?.pending_entry??paper.account?.pending_exit
 const operationalSymbol=operational?.symbol??symbol,operationalTimeframe=operational?.timeframe??timeframe
 const authoritativeStrategy=paperActive&&autoCycle?.strategy?autoCycle.strategy:completedStrategy

 useEffect(()=>{
   if(!paperActive||!autoRefresh||autoCycleInFlight.current)return
   autoCycleInFlight.current=true
   let active=true
   void tradingGuardApi.autoPaperCycle(operationalSymbol,operationalTimeframe,source,0.5,20).then(result=>{
     if(!active)return
     setAutoCycle(result);setAutoCycleError(null);void paperRefresh()
   }).catch((cause:unknown)=>{
     if(!active)return
     setAutoCycleError(cause instanceof Error?cause.message:'Siklus Auto Paper gagal.')
   }).finally(()=>{autoCycleInFlight.current=false})
   return()=>{active=false}
 },[paperActive,autoRefresh,refreshKey,operationalSymbol,operationalTimeframe,source,paperRefresh])

 const controls=<div className="panel-soft flex flex-wrap items-end gap-3 rounded p-4"><label className="text-xs"><span className="mono mb-1 block text-[9px] text-slate-500">SUMBER</span><select value={source} onChange={e=>setSource(e.target.value as MarketSource)} className="rounded border border-slate-700 bg-slate-900 px-3 py-2"><option value="binance">REAL · Binance Public</option><option value="mock">MOCK · Deterministik</option></select></label><label className="text-xs"><span className="mono mb-1 block text-[9px] text-slate-500">SIMBOL</span><select value={symbol} onChange={e=>setSymbol(e.target.value)} className="rounded border border-slate-700 bg-slate-900 px-3 py-2"><option>BTCUSDT</option><option>ETHUSDT</option><option>BNBUSDT</option></select></label><div><span className="mono mb-1 block text-[9px] text-slate-500">RENTANG CHART</span><div className="flex overflow-hidden rounded border border-slate-700">{(['1H','4H','1D','1W','1M'] as ChartRange[]).map(range=><button key={range} onClick={()=>setChartRange(range)} className={`px-3 py-2 text-xs ${chartRange===range?'bg-sky-500/15 text-sky-300':'bg-slate-900 text-slate-500 hover:text-slate-300'}`}>{range}</button>)}</div><div className="mono mt-1 text-[8px] text-slate-600">RESOLUSI CANDLE · {timeframe}</div></div>{real&&<div className="rounded border border-emerald-500/20 bg-emerald-500/5 px-3 py-2"><div className="mono text-[8px] text-slate-500">HARGA LIVE · WEBSOCKET</div><div className="mono text-sm font-bold text-white">{live.price===null?'—':live.price.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:8})} USDT</div><div className={`mono text-[8px] ${live.connected?'text-emerald-400':'text-amber-400'}`}>● {live.connected?'STREAMING':'MENGHUBUNGKAN ULANG'}</div></div>}<button disabled={loading} onClick={()=>setRefreshKey(v=>v+1)} className="flex items-center gap-2 rounded border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-300 disabled:opacity-50"><RefreshCw size={14} className={loading?'animate-spin':''}/>{loading?'Memuat…':'Perbarui'}</button><button onClick={()=>setAutoRefresh(v=>!v)} className={`flex items-center gap-2 rounded border px-3 py-2 text-xs ${autoRefresh?'border-emerald-500/30 bg-emerald-500/10 text-emerald-300':'border-slate-700 bg-slate-900 text-slate-400'}`}>{autoRefresh?<Pause size={14}/>:<Play size={14}/>} {autoRefresh?`SINKRON ANALISIS · ${MARKET_REFRESH_SECONDS}s`:'ANALISIS DIJEDA'}</button></div>
 const autoControl=<AutoPaperControl paper={paper} strategy={authoritativeStrategy} referencePrice={completedCandle?.close} externalResult={paperActive?autoCycle:null}/>
 const runtime=<PositionRuntimePanel cycle={paperActive?autoCycle:null}/>
 const content:Record<View,ReactNode>={Dashboard:<DashboardIndonesia selection={selection} candle={completedCandle} indicator={completedIndicator} strategy={authoritativeStrategy} loading={loading}/>,Market:<div className="space-y-4"><MarketChart candles={data.candles} indicators={data.indicators} symbol={symbol} timeframe={`${chartRange} view · ${timeframe} candles`}/><MarketView candles={data.candles} symbol={symbol}/></div>,Strategy:<div className="space-y-4"><StrategyView strategy={authoritativeStrategy} loading={loading}/><StrategyTransitionHistory results={data.strategies.slice(0,-1)}/></div>,'Risk Guard':<div className="space-y-4"><RiskGuardIndonesia strategy={authoritativeStrategy} autoCycle={paperActive?autoCycle:null}/>{runtime}{autoControl}</div>,'Paper Trading':<div className="space-y-4"><PaperTradingIndonesia paper={paper} autoCycle={paperActive?autoCycle:null}/>{runtime}{autoControl}</div>,Backtest:<BacktestView backtest={backtest} candles={data.candles} strategies={data.strategies} loading={loading}/>,'Trade Journal':<TradeJournalView paper={paper}/>,Settings:<SettingsView selection={selection}/>}
 return <div className="app-shell min-h-screen text-slate-200"><aside className="sidebar fixed inset-y-0 left-0 w-[238px] px-4 py-6"><div className="mb-8 flex items-center gap-3"><div className="grid size-9 place-items-center rounded bg-sky-500/15 text-sky-300"><ShieldCheck size={20}/></div><div><div className="font-bold text-white">TradingGuard</div><div className="mono text-[10px] text-slate-500">CONTROL CENTER · v0.9</div></div></div><div className="mono mb-3 text-[9px] uppercase tracking-[.2em] text-slate-600">OPERASI</div>{nav.map(item=>{const Icon=item.icon;return <button key={item.name} onClick={()=>setView(item.name)} className={`nav-item mb-1 flex w-full items-center gap-2 rounded px-3 py-2.5 text-left text-xs ${view===item.name?'active':''}`}><Icon size={14}/>{item.label}</button>})}<div className="panel-soft absolute bottom-5 left-4 right-4 rounded p-3 text-[10px] text-slate-500">Kontrol backend-authoritative. PAPER only; tanpa eksekusi broker.</div></aside><main className="main-area ml-[238px] min-h-screen px-8 py-6"><header className="mb-6 border-b border-slate-800 pb-5"><div className="mb-5 flex flex-wrap items-center justify-between gap-4"><div><div className="mono text-[10px] uppercase tracking-[.18em] text-slate-500">Pusat kontrol risiko</div><h1 className="text-2xl font-bold text-white">{title[view]}</h1></div><div className={`rounded border px-3 py-2 mono text-[10px] ${real?'border-sky-500/30 bg-sky-500/10 text-sky-300':'border-amber-500/30 bg-amber-500/10 text-amber-300'}`}>● {real?'DATA PUBLIK REAL · BINANCE':'DATA MOCK'}</div></div>{controls}</header>{error&&<div className="mb-5 rounded border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-200">Sumber data tidak tersedia: {error}. Tidak ada fallback diam-diam ke data mock.</div>}{live.error&&real&&<div className="mb-5 rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">{live.error} Data historis REST tetap terpisah; tidak ada fallback ke mock.</div>}{autoCycleError&&paperActive&&<div className="mb-5 rounded border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-200">Auto Paper fail-closed: {autoCycleError}</div>}{content[view]}<footer className="mt-6 border-t border-slate-800 py-5 mono text-[9px] text-slate-600">SUMBER: {real?'BINANCE PUBLIC REST + PUBLIC WEBSOCKET':'TRADINGGUARD MOCK DETERMINISTIK'} · {real?(live.connected?'STREAM LIVE TERHUBUNG':'STREAM MENGHUBUNGKAN ULANG'):'TANPA STREAM LIVE'} · SINKRON ANALISIS {autoRefresh?`${MARKET_REFRESH_SECONDS}s`:'DIJEDA'} · CHART {chartRange}/{timeframe} · AUTO PAPER {paperActive?'AKTIF':'NONAKTIF'} · KONTROL RISIKO PAPER · TANPA EKSEKUSI BROKER</footer></main></div>
}
export default App
