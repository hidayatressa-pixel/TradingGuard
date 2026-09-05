from datetime import datetime

from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from backend.app.indicators.models import IndicatorSnapshot
from backend.app.indicators.service import IndicatorService
from backend.app.market.data_provider import MockMarketDataProvider
from backend.app.market.models import Candle
from backend.app.market.validation import validate_candle_dataset
from backend.app.risk.models import RiskContext, RiskPolicy, RiskResult
from backend.app.risk.service import RiskService
from backend.app.strategy.models import Assessment, StrategyEvidence, StrategyResult
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

app = FastAPI(title="TradingGuard", version="0.5.0")
provider = MockMarketDataProvider()
indicator_service = IndicatorService()
strategy_service = StrategyService()
risk_service = RiskService()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "TradingGuard",
        "message": "Application is running.",
    }


@app.get("/market/candles", response_model=list[Candle])
def get_market_candles(
    symbol: str = Query(..., min_length=1, description="Trading symbol to request, for example BTCUSD."),
    timeframe: str = Query(..., pattern=r"^(1m|5m|15m|1h|4h|1d)$", description="Candle timeframe."),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of candles to return."),
) -> list[Candle]:
    try:
        candles = provider.get_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    validation_errors = validate_candle_dataset(candles)
    if validation_errors:
        raise HTTPException(status_code=500, detail=validation_errors)

    return candles


@app.get("/indicators", response_model=list[IndicatorSnapshot])
def get_indicators(
    symbol: str = Query(..., min_length=1, description="Trading symbol to request, for example BTCUSD."),
    timeframe: str = Query(..., pattern=r"^(1m|5m|15m|1h|4h|1d)$", description="Candle timeframe."),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of candles to return."),
) -> list[IndicatorSnapshot]:
    try:
        candles = provider.get_candles(symbol=symbol, timeframe=timeframe, limit=limit)
        snapshots = indicator_service.build_snapshots(candles)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return snapshots


@app.get("/strategy", response_model=list[StrategyResult])
def get_strategy(
    symbol: str = Query(..., min_length=1, description="Trading symbol to request, for example BTCUSD."),
    timeframe: str = Query(..., pattern=r"^(1m|5m|15m|1h|4h|1d)$", description="Candle timeframe."),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of candles to return."),
) -> list[StrategyResult]:
    try:
        candles = provider.get_candles(symbol=symbol, timeframe=timeframe, limit=limit)
        snapshots = indicator_service.build_snapshots(candles)
        results = strategy_service.build_results(snapshots)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return results


@app.post("/risk/evaluate", response_model=RiskResult)
def evaluate_risk(
    payload: dict = Body(...),
) -> RiskResult:
    try:
        request = RiskEvaluateRequest.model_validate(payload)
        strategy_payload = request.strategy.model_dump()
        strategy_payload["timestamp"] = datetime.fromisoformat(str(strategy_payload["timestamp"]).replace("Z", "+00:00"))
        strategy_payload["assessment"] = Assessment(strategy_payload["assessment"])

        for evidence in strategy_payload.get("evidence", []):
            evidence["indicator"] = str(evidence["indicator"])
            evidence["condition"] = str(evidence["condition"])
            evidence["description"] = str(evidence["description"])

        strategy = StrategyResult.model_validate(strategy_payload)
        context = RiskContext.model_validate(request.context)
        policy = RiskPolicy.model_validate(request.policy or {})
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return risk_service.evaluate(strategy, context, policy)
