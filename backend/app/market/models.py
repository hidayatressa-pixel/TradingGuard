from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class Candle(BaseModel):
    """Normalized OHLCV candle model used by the market data layer."""

    model_config = ConfigDict(strict=True)

    timestamp: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware.")
        return value

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("symbol must be a non-empty string.")
        return value.strip().upper()

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("timeframe must be a non-empty string.")
        return value.strip().lower()

    @field_validator("open", "high", "low", "close")
    @classmethod
    def validate_price_fields(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("prices must be finite and positive.")
        return float(value)

    @field_validator("volume")
    @classmethod
    def validate_volume(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("volume must be finite and greater than or equal to zero.")
        return float(value)

    @model_validator(mode="after")
    def validate_ohlc_relationships(self) -> "Candle":
        if self.high < self.open:
            raise ValueError("high must be greater than or equal to open.")
        if self.high < self.close:
            raise ValueError("high must be greater than or equal to close.")
        if self.low > self.open:
            raise ValueError("low must be less than or equal to open.")
        if self.low > self.close:
            raise ValueError("low must be less than or equal to close.")
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low.")
        return self
