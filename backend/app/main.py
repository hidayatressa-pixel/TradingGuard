from fastapi import FastAPI, HTTPException, Query

from backend.app.market.data_provider import MockMarketDataProvider
from backend.app.market.models import Candle
from backend.app.market.validation import validate_candle_dataset

app = FastAPI(title="TradingGuard", version="0.1.0")
provider = MockMarketDataProvider()


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
