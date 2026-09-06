from datetime import datetime

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
from backend.app.paper.models import PaperAccount, PaperPerformanceSnapshot, PaperTradingConfig
from backend.app.paper.orchestration import AutoPaperEntryOrchestrator, AutoPaperEntryResult
from backend.app.paper.service import PaperTradingService
from backend.app.risk.context import PaperRiskContextBuilder, RiskContextAvailability
from backend.app.risk.models import RiskContext, RiskPolicy, RiskResult
from backend.app.risk.service import RiskService
from backend.app.risk_sizing.models import RiskSizingRequest, RiskSizingResult
from backend.app.risk_sizing.service import RiskSizingService
from backend.app.strategy.models import Assessment, StrategyResult
from backend.app.strategy.service import StrategyService


class StrategyEvidenceInput(BaseModel):
    model_config = ConfigDict()
    indicator: str
    condition: str
    contribution: int
    description: str


class StrategyResultInput(BaseModel):
    model_config = ConfigDict()
    timestamp: datetime | str
    symbol: str
    timeframe: str
    score: int
    normalized_score: int
    assessment: Assessment | str
    data_ready: bool
    evidence: list[StrategyEvidenceInput]


class RiskEvaluateRequest(BaseModel):
    model_config = ConfigDict()
    strategy: StrategyResultInput
    context: dict
    policy: dict | None = None


class BacktestEvaluateRequest(BaseModel):
    model_config = ConfigDict()
    candles: list[dict]
    strategy_results: list[dict]
    config: dict | None = None


class PaperStartRequest(BaseModel):
    model_config = ConfigDict()
    config: dict | None = None


class PaperProcessRequest(BaseModel):
    model_config = ConfigDict()
    candle: dict
    strategy: dict
    risk: dict


class AutoPaperEntryRequest(BaseModel):
    model_config = ConfigDict()
    strategy: StrategyResultInput
    reference_entry_price: float
    stop_loss_price: float
    risk_budget_pct: float
    max_allocation_pct: float | None = None
    policy: dict | None = None


app = FastAPI(title="TradingGuard", version="0.9.0-dev")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)
mock_provider = MockMarketDataProvider()
real_provider = BinancePublicMarketDataProvider()
indicator_service = IndicatorService()
strategy_service = StrategyService()
risk_service = RiskService()
risk_sizing_service = RiskSizingService()
risk_context_builder = PaperRiskContextBuilder()
backtest_service = BacktestService()
paper_service = PaperTradingService()
auto_paper_orchestrator = AutoPaperEntryOrchestrator(paper_service)


def _provider(source: str) -> MarketDataProvider:
    if source == "mock": return mock_provider
    if source == "binance": return real_provider
    raise HTTPException(status_code=400, detail=f"Unsupported market source: {source}")


def _candles(source: str, symbol: str, timeframe: str, limit: int) -> list[Candle]:
    try: candles = _provider(source).get_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(status_code=502, detail=str(exc)) from exc
    errors = validate_candle_dataset(candles)
    if errors: raise HTTPException(status_code=502 if source != "mock" else 500, detail=errors)
    return candles


@app.get("/health")
def health_check() -> dict[str, str]: return {"status":"ok","service":"TradingGuard","message":"Application is running."}


@app.get("/market/candles", response_model=list[Candle])
def get_market_candles(symbol: str=Query(...,min_length=1), timeframe: str=Query(...,pattern=r"^(1m|5m|15m|1h|4h|1d)$"), limit: int=Query(100,ge=1,le=500), source: str=Query("mock",pattern=r"^(mock|binance)$")) -> list[Candle]: return _candles(source,symbol,timeframe,limit)


@app.get("/indicators", response_model=list[IndicatorSnapshot])
def get_indicators(symbol: str=Query(...,min_length=1), timeframe: str=Query(...,pattern=r"^(1m|5m|15m|1h|4h|1d)$"), limit: int=Query(100,ge=1,le=500), source: str=Query("mock",pattern=r"^(mock|binance)$")) -> list[IndicatorSnapshot]:
    try: return indicator_service.build_snapshots(_candles(source,symbol,timeframe,limit))
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc


@app.get("/strategy", response_model=list[StrategyResult])
def get_strategy(symbol: str=Query(...,min_length=1), timeframe: str=Query(...,pattern=r"^(1m|5m|15m|1h|4h|1d)$"), limit: int=Query(100,ge=1,le=500), source: str=Query("mock",pattern=r"^(mock|binance)$")) -> list[StrategyResult]:
    try: return strategy_service.build_results(indicator_service.build_snapshots(_candles(source,symbol,timeframe,limit)))
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc


@app.post("/risk-sizing/evaluate", response_model=RiskSizingResult)
def evaluate_risk_sizing(request: RiskSizingRequest) -> RiskSizingResult:
    try: return risk_sizing_service.evaluate(request)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/risk/context-availability", response_model=RiskContextAvailability)
def get_risk_context_availability(risk_per_trade_pct: float | None=Query(default=None)) -> RiskContextAvailability:
    try:
        account = paper_service.state()
    except ValueError:
        return RiskContextAvailability(available=False, context=None, missing_facts=["paper_account","risk_per_trade_pct","daily_loss_pct","current_drawdown_pct"], reason="Paper account is not started; complete authoritative RiskContext is unavailable and entry remains fail-closed.")
    return risk_context_builder.build(account, risk_per_trade_pct)


@app.post("/risk/evaluate", response_model=RiskResult)
def evaluate_risk(payload: dict=Body(...)) -> RiskResult:
    try:
        request=RiskEvaluateRequest.model_validate(payload); strategy_payload=request.strategy.model_dump(); strategy_payload["timestamp"]=datetime.fromisoformat(str(strategy_payload["timestamp"]).replace("Z","+00:00")); strategy_payload["assessment"]=Assessment(strategy_payload["assessment"])
        for evidence in strategy_payload.get("evidence",[]): evidence["indicator"]=str(evidence["indicator"]); evidence["condition"]=str(evidence["condition"]); evidence["description"]=str(evidence["description"])
        strategy=StrategyResult.model_validate(strategy_payload); context=RiskContext.model_validate(request.context); policy=RiskPolicy.model_validate(request.policy or {})
    except (KeyError,ValueError,TypeError) as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return risk_service.evaluate(strategy,context,policy)


@app.post("/backtest/evaluate", response_model=BacktestResult)
def evaluate_backtest(payload: dict=Body(...)) -> BacktestResult:
    try:
        request=BacktestEvaluateRequest.model_validate(payload); candles_payload=[]
        for item in request.candles:
            candle=dict(item); candle["timestamp"]=datetime.fromisoformat(str(candle["timestamp"]).replace("Z","+00:00")); candles_payload.append(candle)
        candles=[Candle.model_validate(item) for item in candles_payload]; strategy_results=[]
        for item in request.strategy_results:
            strategy_payload=dict(item); strategy_payload["timestamp"]=datetime.fromisoformat(str(strategy_payload["timestamp"]).replace("Z","+00:00")); strategy_payload["assessment"]=Assessment(strategy_payload["assessment"])
            for evidence in strategy_payload.get("evidence",[]): evidence["indicator"]=str(evidence["indicator"]); evidence["condition"]=str(evidence["condition"]); evidence["description"]=str(evidence["description"])
            strategy_results.append(StrategyResult.model_validate(strategy_payload))
        return backtest_service.evaluate(candles,strategy_results,BacktestConfig.model_validate(request.config or {}))
    except (KeyError,ValueError,TypeError) as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc


def _parse_strategy(payload: dict) -> StrategyResult:
    strategy_payload=dict(payload); strategy_payload["timestamp"]=datetime.fromisoformat(str(strategy_payload["timestamp"]).replace("Z","+00:00")); strategy_payload["assessment"]=Assessment(strategy_payload["assessment"])
    for evidence in strategy_payload.get("evidence",[]): evidence["indicator"]=str(evidence["indicator"]); evidence["condition"]=str(evidence["condition"]); evidence["description"]=str(evidence["description"])
    return StrategyResult.model_validate(strategy_payload)


def _parse_risk(payload: dict) -> RiskResult:
    risk_payload=dict(payload); risk_payload["timestamp"]=datetime.fromisoformat(str(risk_payload["timestamp"]).replace("Z","+00:00")); return RiskResult.model_validate(risk_payload)


@app.post("/paper/start",response_model=PaperAccount)
def start_paper(payload: dict|None=Body(default=None))->PaperAccount:
    try:
        request=PaperStartRequest.model_validate(payload or {}); return paper_service.start(PaperTradingConfig.model_validate(request.config or {}))
    except (KeyError,ValueError,TypeError) as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc


@app.post("/paper/auto-entry", response_model=AutoPaperEntryResult)
def auto_paper_entry(payload: dict=Body(...)) -> AutoPaperEntryResult:
    try:
        request=AutoPaperEntryRequest.model_validate(payload)
        strategy=_parse_strategy(request.strategy.model_dump())
        policy=RiskPolicy.model_validate(request.policy or {})
        return auto_paper_orchestrator.evaluate_and_schedule(
            strategy=strategy,
            reference_entry_price=request.reference_entry_price,
            stop_loss_price=request.stop_loss_price,
            risk_budget_pct=request.risk_budget_pct,
            max_allocation_pct=request.max_allocation_pct,
            policy=policy,
        )
    except (KeyError,ValueError,TypeError) as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


@app.post("/paper/process",response_model=PaperAccount)
def process_paper(payload: dict=Body(...))->PaperAccount:
    try:
        request=PaperProcessRequest.model_validate(payload); candle_payload=dict(request.candle); candle_payload["timestamp"]=datetime.fromisoformat(str(candle_payload["timestamp"]).replace("Z","+00:00")); candle=Candle.model_validate(candle_payload); return paper_service.process_candle(candle,_parse_strategy(request.strategy),_parse_risk(request.risk))
    except (KeyError,ValueError,TypeError) as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc


@app.get("/paper/state",response_model=PaperAccount)
def get_paper_state()->PaperAccount:
    try: return paper_service.state()
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc


@app.get("/paper/performance",response_model=PaperPerformanceSnapshot)
def get_paper_performance()->PaperPerformanceSnapshot:
    try: return paper_service.performance()
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc


@app.post("/paper/reset",response_model=PaperAccount)
def reset_paper()->PaperAccount: return paper_service.reset()
