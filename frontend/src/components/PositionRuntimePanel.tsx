import type { AutoPaperCycleResult } from '../api/types'
import { TrafficLightStatus, type TrafficLightTone } from './TrafficLightStatus'

const money=(value:number|null|undefined)=>value==null?'—':`${value>=0?'+':''}${value.toFixed(2)} USDT`
const pct=(value:number|null|undefined)=>value==null?'—':`${value>=0?'+':''}${value.toFixed(3)}%`

export function PositionRuntimePanel({cycle}:{cycle?:AutoPaperCycleResult|null}){
 const position=cycle?.account.open_position
 if(!position)return null
 const current=cycle.strategy.assessment
 const exit=cycle.account.pending_exit
 const auth=cycle.authorization?.gate?.risk?.decision
 let tone:TrafficLightTone='green',label='MONITORING POSISI',detail='Posisi aktif; Stop Loss dan aturan exit dievaluasi pada candle authoritative.'
 if(exit){tone='red';label='EXIT ARMED';detail=`Strategy completed saat ini ${current}. Exit sudah dijadwalkan oleh backend; ini bukan status entry ALLOW.`}
 else if(current==='BEARISH'||current==='STRONG_BEARISH'){tone='red';label='RISIKO POSISI MENINGKAT';detail=`Strategy completed saat ini ${current}. Backend wajib mengaktifkan jalur exit.`}
 else if(current==='NEUTRAL'){tone='yellow';label='POSISI · KONDISI NETRAL';detail='Momentum entry sudah hilang; backend memonitor jalur exit.'}
 return <section className="panel rounded-lg p-5"><div className="mono text-[9px] font-semibold text-sky-300">CURRENT POSITION RISK · BUKAN ENTRY AUTHORIZATION</div><div className="mt-4"><TrafficLightStatus tone={tone} label={label} detail={detail}/></div><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">{[
  ['ENTRY AUTH',auth??'—'],['STRATEGY SEKARANG',current.replace(/_/g,' ')],['MARK PRICE',cycle.mark_price==null?'—':`${cycle.mark_price.toLocaleString()} USDT`],['P/L BELUM TEREALISASI',money(cycle.unrealized_pnl)],['RETURN OPEN',pct(cycle.unrealized_return_pct)],['EXIT STATE',exit?'PENDING EXIT':'MONITORING']
 ].map(([name,value])=><div key={name} className="panel-soft rounded p-3"><div className="mono text-[8px] text-sky-300">{name}</div><div className="mt-2 text-sm font-bold text-white">{value}</div></div>)}</div><p className="mt-4 text-xs text-slate-400">Entry ALLOW adalah catatan historis izin membuka posisi. Strategy sekarang dan EXIT STATE adalah kondisi operasional yang terus berubah.</p></section>
}
