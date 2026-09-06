import{useCallback,useState}from'react'
import{tradingGuardApi,type MarketSource}from'./client'
import type{AutoPaperCycleResult}from'./types'

export function useAutoPaper(){
 const[result,setResult]=useState<AutoPaperCycleResult|null>(null),[running,setRunning]=useState(false),[error,setError]=useState<string|null>(null)
 const evaluate=useCallback(async(symbol:string,timeframe:string,source:MarketSource='binance',riskBudget=0.5,maxAllocation=20)=>{setRunning(true);setError(null);try{const next=await tradingGuardApi.autoPaperCycle(symbol,timeframe,source,riskBudget,maxAllocation);setResult(next);return next}catch(cause:unknown){const message=cause instanceof Error?cause.message:'Siklus Auto Paper gagal.';setError(message);throw cause}finally{setRunning(false)}},[])
 const clear=useCallback(()=>{setResult(null);setError(null)},[])
 return{result,running,error,evaluate,clear}
}
