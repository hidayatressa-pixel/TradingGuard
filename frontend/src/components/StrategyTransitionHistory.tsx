import type { Assessment, StrategyResult } from '../api/types'

type Transition = {
  timestamp: string
  from: Assessment
  to: Assessment
  score: number
  normalizedScore: number
}

function transitions(results: StrategyResult[]): Transition[] {
  const output: Transition[] = []
  for (let index = 1; index < results.length; index += 1) {
    const previous = results[index - 1]
    const current = results[index]
    if (previous.assessment !== current.assessment) {
      output.push({
        timestamp: current.timestamp,
        from: previous.assessment,
        to: current.assessment,
        score: current.score,
        normalizedScore: current.normalized_score,
      })
    }
  }
  return output.slice(-12).reverse()
}

const label = (value: Assessment) => value.replace(/_/g, ' ')

export function StrategyTransitionHistory({ results }: { results: StrategyResult[] }) {
  const history = transitions(results)
  const current = results.at(-1)

  return <section className="panel rounded-lg p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div className="mono text-[9px] text-slate-500">BACKEND STRATEGY TIMELINE</div>
        <h2 className="mt-1 text-lg font-semibold text-white">Strategy Transition History</h2>
        <p className="mt-2 text-xs text-slate-500">Shows changes between backend StrategyResult assessments. This is observation history, not execution permission.</p>
      </div>
      <div className="rounded border border-slate-800 px-3 py-2 text-right">
        <div className="mono text-[8px] text-slate-600">CURRENT</div>
        <div className="mt-1 text-xs font-semibold text-sky-300">{current ? label(current.assessment) : 'N/A'}</div>
      </div>
    </div>
    {history.length ? <div className="mt-5 overflow-x-auto"><table className="w-full text-left text-xs"><thead className="mono text-[9px] text-slate-500"><tr><th className="px-3 py-3">TIME</th><th className="px-3 py-3">FROM</th><th className="px-3 py-3">TO</th><th className="px-3 py-3">SCORE</th><th className="px-3 py-3">NORMALIZED</th></tr></thead><tbody>{history.map(item => <tr className="border-t border-slate-800" key={`${item.timestamp}-${item.from}-${item.to}`}><td className="px-3 py-3 text-slate-500">{new Date(item.timestamp).toLocaleString()}</td><td className="px-3 py-3 text-slate-400">{label(item.from)}</td><td className="px-3 py-3 font-semibold text-sky-300">{label(item.to)}</td><td className="px-3 py-3">{item.score}</td><td className="px-3 py-3">{item.normalizedScore}%</td></tr>)}</tbody></table></div> : <div className="mt-5 rounded border border-slate-800 p-4 text-xs text-slate-500">No assessment transition exists in the currently loaded backend sequence.</div>}
    <div className="mt-4 mono text-[8px] text-slate-600">DERIVED FOR DISPLAY FROM BACKEND STRATEGY RESULTS · NO FRONTEND SIGNAL CALCULATION · NO BUY/SELL AUTHORIZATION</div>
  </section>
}
