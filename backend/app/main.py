from datetime import datetime
import os

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from backend.app.backtest.models import BacktestConfig, BacktestResult
from backend.app.backtest.service import BacktestService
from backend.app.indicators.models import IndicatorSnapshot
from backend.app.indicators.service import IndicatorService
from backend.app.market.data_provider import BinancePublicMarketDataProvider, MarketDataProvider, MockMarketDataProvider
from backend.app.market.models import Candle
from backend.app.market.validation import validate_candle_dataset
from backend.app.paper.auto_loop import AutoPaperCycleResult, AutoPaperLoopService
from backend.app.paper.manual import ManualGuardedTradeResult, ManualGuardedTradeService
from backend.app.paper.models import PaperAccount, PaperPerformanceSnapshot, PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.context import PaperRiskContextBuilder, RiskContextAvailability
from backend.app.risk.models import RiskContext, RiskPolicy, RiskResult
from backend.app.risk.service import RiskService
from backend.app.risk_sizing.models import RiskSizingRequest, RiskSizingResult
from backend.app.risk_sizing.service import RiskSizingService
from backend.app.strategy.models import Assessment, StrategyResult
from backend.app.strategy.service import StrategyService

class StrategyEvidenceInput(BaseModel):
    model_config=ConfigDict(); indicator:str; condition:str; contribution:int; description:str
class StrategyResultInput(BaseModel):
    model_config=ConfigDict(); timestamp:datetime|str; symbol:str; timeframe:str; score:int; normalized_score:int; assessment:Assessment|str; data_ready:bool; evidence:list[StrategyEvidenceInput]
class RiskEvaluateRequest(BaseModel):
    model_config=ConfigDict(); strategy:StrategyResultInput; context:dict; policy:dict|None=None
class BacktestEvaluateRequest(BaseModel):
    model_config=ConfigDict(); candles:list[dict]; strategy_results:list[dict]; config:dict|None=None
class PaperStartRequest(BaseModel):
    model_config=ConfigDict(); config:dict|None=None
class PaperProcessRequest(BaseModel):
    model_config=ConfigDict(); candle:dict; strategy:dict; risk:dict

def _cors_origins()->list[str]:
    configured=os.getenv('CORS_ORIGINS','')
    origins=[origin.strip().rstrip('/') for origin in configured.split(',') if origin.strip()]
    return origins or ['http://localhost:5173','http://127.0.0.1:5173']

app=FastAPI(title='TradingGuard',version='0.9.0-dev')
app.add_middleware(CORSMiddleware,allow_origins=_cors_origins(),allow_credentials=False,allow_methods=['GET','POST','OPTIONS'],allow_headers=['Content-Type','Accept'])
mock_provider=MockMarketDataProvider(); real_provider=BinancePublicMarketDataProvider(); indicator_service=IndicatorService(); strategy_service=StrategyService(); risk_service=RiskService(); risk_sizing_service=RiskSizingService(); risk_context_builder=PaperRiskContextBuilder(); backtest_service=BacktestService(); paper_service=PaperTradingService(); auto_paper_loop=AutoPaperLoopService(paper_service); manual_trade_service=ManualGuardedTradeService(paper_service)

def _provider(source:str)->MarketDataProvider:
    if source=='mock': return mock_provider
    if source=='binance': return real_provider
    raise HTTPException(status_code=400,detail=f'Unsupported market source: {source}')
def _candles(source:str,symbol:str,timeframe:str,limit:int)->list[Candle]:
    try: candles=_provider(source).get_candles(symbol=symbol,timeframe=timeframe,limit=limit)
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(status_code=502,detail=str(exc)) from exc
    errors=validate_candle_dataset(candles)
    if errors: raise HTTPException(status_code=502 if source!='mock' else 500,detail=errors)
    return candles

def _authoritative_market(source:str,symbol:str,timeframe:str,limit:int=100):
    candles=_candles(source,symbol,timeframe,limit)
    if len(candles)<2: raise HTTPException(status_code=422,detail='At least one completed candle and one market observation are required.')
    completed=candles[:-1]
    strategies=strategy_service.build_results(indicator_service.build_snapshots(completed))
    if not strategies: raise HTTPException(status_code=422,detail='Strategy is unavailable for completed candles.')
    return candles,completed,strategies[-1]

@app.get('/health')
def health_check()->dict[str,str]: return {'status':'ok','service':'TradingGuard','message':'Application is running.'}
@app.get('/market/candles',response_model=list[Candle])
def get_market_candles(symbol:str=Query(...,min_length=1),timeframe:str=Query(...,pattern=r'^(1m|5m|15m|1h|4h|1d)$'),limit:int=Query(100,ge=1,le=500),source:str=Query('mock',pattern=r'^(mock|binance)$'))->list[Candle]: return _candles(source,symbol,timeframe,limit)
@app.get('/indicators',response_model=list[IndicatorSnapshot])
def get_indicators(symbol:str=Query(...,min_length=1),timeframe:str=Query(...,pattern=r'^(1m|5m|15m|1h|4h|1d)$'),limit:int=Query(100,ge=1,le=500),source:str=Query('mock',pattern=r'^(mock|binance)$'))->list[IndicatorSnapshot]: return indicator_service.build_snapshots(_candles(source,symbol,timeframe,limit))
@app.get('/strategy',response_model=list[StrategyResult])
def get_strategy(symbol:str=Query(...,min_length=1),timeframe:str=Query(...,pattern=r'^(1m|5m|15m|1h|4h|1d)$'),limit:int=Query(100,ge=1,le=500),source:str=Query('mock',pattern=r'^(mock|binance)$'))->list[StrategyResult]: return strategy_service.build_results(indicator_service.build_snapshots(_candles(source,symbol,timeframe,limit)))
@app.post('/risk-sizing/evaluate',response_model=RiskSizingResult)
def evaluate_risk_sizing(request:RiskSizingRequest)->RiskSizingResult:
    try:return risk_sizing_service.evaluate(request)
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
@app.get('/risk/context-availability',response_model=RiskContextAvailability)
def get_risk_context_availability(risk_per_trade_pct:float|None=Query(default=None))->RiskContextAvailability:
    try: account=paper_service.state()
    except ValueError:return RiskContextAvailability(available=False,context=None,missing_facts=['paper_account','risk_per_trade_pct','daily_loss_pct','current_drawdown_pct'],reason='Paper account is not started; complete authoritative RiskContext is unavailable and entry remains fail-closed.')
    return risk_context_builder.build(account,risk_per_trade_pct)
@app.post('/risk/evaluate',response_model=RiskResult)
def evaluate_risk(payload:dict=Body(...))->RiskResult:
    try:
        r=RiskEvaluateRequest.model_validate(payload); s=_parse_strategy(r.strategy.model_dump()); c=RiskContext.model_validate(r.context); p=RiskPolicy.model_validate(r.policy or {})
    except (KeyError,ValueError,TypeError) as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
    return risk_service.evaluate(s,c,p)
@app.post('/backtest/evaluate',response_model=BacktestResult)
def evaluate_backtest(payload:dict=Body(...))->BacktestResult:
    try:
        r=BacktestEvaluateRequest.model_validate(payload); candles=[]
        for item in r.candles:
            x=dict(item);x['timestamp']=datetime.fromisoformat(str(x['timestamp']).replace('Z','+00:00'));candles.append(Candle.model_validate(x))
        strategies=[_parse_strategy(x) for x in r.strategy_results]
        return backtest_service.evaluate(candles,strategies,BacktestConfig.model_validate(r.config or {}))
    except (KeyError,ValueError,TypeError) as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
def _parse_strategy(payload:dict)->StrategyResult:
    x=dict(payload);x['timestamp']=datetime.fromisoformat(str(x['timestamp']).replace('Z','+00:00'));x['assessment']=Assessment(x['assessment'])
    for e in x.get('evidence',[]):e['indicator']=str(e['indicator']);e['condition']=str(e['condition']);e['description']=str(e['description'])
    return StrategyResult.model_validate(x)
def _parse_risk(payload:dict)->RiskResult:
    x=dict(payload);x['timestamp']=datetime.fromisoformat(str(x['timestamp']).replace('Z','+00:00'));return RiskResult.model_validate(x)
@app.post('/paper/start',response_model=PaperAccount)
def start_paper(payload:dict|None=Body(default=None))->PaperAccount:
    try:r=PaperStartRequest.model_validate(payload or {});return paper_service.start(PaperTradingConfig.model_validate(r.config or {}))
    except (KeyError,ValueError,TypeError) as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

@app.post('/paper/manual-buy',response_model=ManualGuardedTradeResult)
def manual_paper_buy(symbol:str=Query(...,min_length=1),timeframe:str=Query(...,pattern=r'^(1m|5m|15m|1h|4h|1d)$'),source:str=Query('binance',pattern=r'^(mock|binance)$'),risk_budget_pct:float=Query(0.5,gt=0,le=1.0),max_allocation_pct:float=Query(20.0,gt=0,le=100))->ManualGuardedTradeResult:
    """Interactive PAPER BUY: backend derives strategy/stop/sizing/risk; no client bypass and no pending loop."""
    try:
        candles,completed,strategy=_authoritative_market(source,symbol,timeframe)
        return manual_trade_service.buy(completed_candles=completed,strategy=strategy,market_price=float(candles[-1].close),risk_budget_pct=risk_budget_pct,max_allocation_pct=max_allocation_pct)
    except HTTPException: raise
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc

@app.post('/paper/manual-sell',response_model=ManualGuardedTradeResult)
def manual_paper_sell(source:str=Query('binance',pattern=r'^(mock|binance)$'))->ManualGuardedTradeResult:
    """Close the active PAPER position immediately using authoritative market data."""
    try:
        account=paper_service.state(); position=account.open_position
        if position is None: raise HTTPException(status_code=422,detail='No active paper position to SELL.')
        candles,_,strategy=_authoritative_market(source,position.symbol,position.timeframe)
        return manual_trade_service.sell(strategy=strategy,market_price=float(candles[-1].close))
    except HTTPException: raise
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc

@app.post('/paper/auto-cycle',response_model=AutoPaperCycleResult)
def auto_paper_cycle(symbol:str=Query(...,min_length=1),timeframe:str=Query(...,pattern=r'^(1m|5m|15m|1h|4h|1d)$'),source:str=Query('binance',pattern=r'^(mock|binance)$'),limit:int=Query(100,ge=35,le=500),risk_budget_pct:float=Query(0.5,gt=0,le=1.0),max_allocation_pct:float=Query(20.0,gt=0,le=100))->AutoPaperCycleResult:
    try:
        account=paper_service.state()
        if not account.active or not account.config.paper_trading_enabled: raise HTTPException(status_code=422,detail='Paper trading is inactive; autonomous evaluation remains fail-closed.')
        return auto_paper_loop.cycle(_candles(source,symbol,timeframe,limit),risk_budget_pct=risk_budget_pct,max_allocation_pct=max_allocation_pct)
    except HTTPException: raise
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
@app.post('/paper/process',response_model=PaperAccount)
def process_paper(payload:dict=Body(...))->PaperAccount:
    try:
        r=PaperProcessRequest.model_validate(payload);x=dict(r.candle);x['timestamp']=datetime.fromisoformat(str(x['timestamp']).replace('Z','+00:00'));return paper_service.process_candle(Candle.model_validate(x),_parse_strategy(r.strategy),_parse_risk(r.risk))
    except (KeyError,ValueError,TypeError) as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
@app.get('/paper/state',response_model=PaperAccount)
def get_paper_state()->PaperAccount:
    try:return paper_service.state()
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
@app.get('/paper/performance',response_model=PaperPerformanceSnapshot)
def get_paper_performance()->PaperPerformanceSnapshot:
    try:return paper_service.performance()
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
@app.post('/paper/reset',response_model=PaperAccount)
def reset_paper()->PaperAccount:return paper_service.reset()