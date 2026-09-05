from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class IndicatorSnapshot(BaseModel):
    """Calculated indicator values aligned to a candle series."""

    model_config = ConfigDict(strict=True)

    timestamp: datetime
    symbol: str
    timeframe: str
    close: float
    ema_fast: float | None = None
    ema_slow: float | None = None
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
