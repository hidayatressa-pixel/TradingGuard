import { useMemo } from 'react'
import type { Candle, IndicatorSnapshot } from '../api/types'

const WIDTH = 1200
const HEIGHT = 430
const PAD = { top: 24, right: 72, bottom: 36, left: 18 }
const PLOT_W = WIDTH - PAD.left - PAD.right
const PLOT_H = HEIGHT - PAD.top - PAD.bottom

type Point = { x: number; y: number }

function linePath(points: Point[]): string {
  return points.map((point, index) => `${index ? 'L' : 'M'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ')
}

export function MarketChart({ candles, indicators, symbol, timeframe }: { candles: Candle[]; indicators: IndicatorSnapshot[]; symbol: string; timeframe: string }) {
  const model = useMemo(() => {
    if (!candles.length) return null
    const visible = candles.slice(-80)
    const indicatorByTimestamp = new Map(indicators.map(item => [item.timestamp, item]))
    const lows = visible.map(item => item.low)
    const highs = visible.map(item => item.high)
    const rawMin = Math.min(...lows)
    const rawMax = Math.max(...highs)
    const span = Math.max(rawMax - rawMin, Math.abs(rawMax) * 0.002, 1)
    const min = rawMin - span * 0.08
    const max = rawMax + span * 0.08
    const y = (price: number) => PAD.top + ((max - price) / (max - min)) * PLOT_H
    const step = PLOT_W / visible.length
    const bodyWidth = Math.max(2, Math.min(10, step * 0.62))
    const rows = visible.map((candle, index) => ({ candle, indicator: indicatorByTimestamp.get(candle.timestamp), x: PAD.left + step * index + step / 2 }))
    const fast = rows.filter(row => row.indicator?.ema_fast != null).map(row => ({ x: row.x, y: y(row.indicator!.ema_fast!) }))
    const slow = rows.filter(row => row.indicator?.ema_slow != null).map(row => ({ x: row.x, y: y(row.indicator!.ema_slow!) }))
    const ticks = Array.from({ length: 5 }, (_, index) => max - ((max - min) * index) / 4)
    return { rows, y, bodyWidth, fast, slow, ticks, min, max }
  }, [candles, indicators])

  if (!model) return <div className="grid h-[430px] place-items-center text-xs text-slate-500">No backend candles available.</div>
  const latest = model.rows.at(-1)?.candle

  return <div className="panel rounded-lg p-5">
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3"><div><div className="mono text-[9px] text-slate-500">BACKEND OHLC · MARKET CHART</div><h2 className="mt-1 text-lg font-semibold text-white">{symbol} · {timeframe}</h2></div><div className="text-right"><div className="mono text-[9px] text-slate-500">LATEST CLOSE</div><div className="mt-1 text-lg font-bold text-white">{latest ? latest.close.toLocaleString(undefined,{maximumFractionDigits:2}) : 'N/A'}</div></div></div>
    <div className="mb-3 flex gap-4 text-[10px] text-slate-500"><span><i className="mr-1 inline-block size-2 rounded-full bg-sky-400"/>EMA Fast</span><span><i className="mr-1 inline-block size-2 rounded-full bg-amber-300"/>EMA Slow</span><span>Green/red candle = backend OHLC direction</span></div>
    <div className="overflow-x-auto rounded border border-slate-800 bg-slate-950/40">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="min-w-[900px] w-full" role="img" aria-label={`${symbol} ${timeframe} candlestick chart`}>
        {model.ticks.map(price => <g key={price}><line x1={PAD.left} x2={WIDTH-PAD.right} y1={model.y(price)} y2={model.y(price)} stroke="currentColor" className="text-slate-800" strokeWidth="1"/><text x={WIDTH-PAD.right+8} y={model.y(price)+4} fill="currentColor" className="text-slate-500" fontSize="10">{price.toLocaleString(undefined,{maximumFractionDigits:2})}</text></g>)}
        {model.rows.map(({ candle, x }) => { const up=candle.close>=candle.open; const top=model.y(Math.max(candle.open,candle.close)); const bottom=model.y(Math.min(candle.open,candle.close)); const bodyHeight=Math.max(1,bottom-top); const tone=up?'#22c55e':'#ef4444'; return <g key={candle.timestamp}><line x1={x} x2={x} y1={model.y(candle.high)} y2={model.y(candle.low)} stroke={tone} strokeWidth="1"/><rect x={x-model.bodyWidth/2} y={top} width={model.bodyWidth} height={bodyHeight} fill={tone}/><title>{`${new Date(candle.timestamp).toLocaleString()} O ${candle.open} H ${candle.high} L ${candle.low} C ${candle.close}`}</title></g> })}
        {model.fast.length>1 && <path d={linePath(model.fast)} fill="none" stroke="#38bdf8" strokeWidth="1.6" opacity=".9"/>}
        {model.slow.length>1 && <path d={linePath(model.slow)} fill="none" stroke="#fde047" strokeWidth="1.6" opacity=".85"/>}
        <text x={PAD.left} y={HEIGHT-12} fill="currentColor" className="text-slate-600" fontSize="10">{new Date(model.rows[0].candle.timestamp).toLocaleString()}</text>
        <text x={WIDTH-PAD.right} y={HEIGHT-12} textAnchor="end" fill="currentColor" className="text-slate-600" fontSize="10">{new Date(model.rows.at(-1)!.candle.timestamp).toLocaleString()}</text>
      </svg>
    </div>
    <p className="mt-3 text-[10px] text-slate-500">Visualization only. Candles and EMA values are supplied by TradingGuard backend; this component does not calculate strategy, risk, or execution permission.</p>
  </div>
}
