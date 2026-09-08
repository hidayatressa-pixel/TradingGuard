import { AlertTriangle, CheckCircle2, CircleStop } from 'lucide-react'

export type TrafficLightTone='red'|'yellow'|'green'

type Props={tone:TrafficLightTone;label:string;detail?:string;compact?:boolean}

const styles:Record<TrafficLightTone,{box:string;text:string;dot:string;Icon:typeof CircleStop}>={
 red:{box:'border-red-400/45 bg-red-500/12',text:'text-red-200',dot:'bg-red-400 shadow-[0_0_16px_rgba(248,113,113,.75)]',Icon:CircleStop},
 yellow:{box:'border-amber-400/45 bg-amber-500/12',text:'text-amber-200',dot:'bg-amber-300 shadow-[0_0_16px_rgba(252,211,77,.65)]',Icon:AlertTriangle},
 green:{box:'border-emerald-400/45 bg-emerald-500/12',text:'text-emerald-200',dot:'bg-emerald-400 shadow-[0_0_16px_rgba(52,211,153,.65)]',Icon:CheckCircle2},
}

export function TrafficLightStatus({tone,label,detail,compact=false}:Props){const style=styles[tone],Icon=style.Icon;return <div className={`rounded-lg border ${style.box} ${compact?'px-3 py-2':'p-4'}`}><div className="flex items-center gap-3"><span className={`size-3 shrink-0 rounded-full ${style.dot}`} aria-hidden="true"/><Icon size={compact?15:18} className={style.text}/><div className={`font-bold tracking-wide ${style.text} ${compact?'text-xs':'text-base'}`}>{label}</div></div>{detail&&<div className={`mt-2 leading-5 text-slate-200 ${compact?'text-[10px]':'text-xs'}`}>{detail}</div>}</div>}
