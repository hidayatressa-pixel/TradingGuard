from __future__ import annotations

from dataclasses import dataclass

from backend.app.market.models import Candle
from backend.app.market.validation import validate_candle_dataset

from .calculator import calculate_ema, calculate_macd, calculate_rsi
from .models import IndicatorSnapshot


@dataclass(frozen=True)
class IndicatorConfig:
    ema_fast: int = 12
    ema_slow: int = 26
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9


class IndicatorService:
    """Build indicator snapshots from normalized candles."""

    def __init__(self, config: IndicatorConfig | None = None) -> None:
        self.config = config or IndicatorConfig()

    def build_snapshots(self, candles: list[Candle]) -> list[IndicatorSnapshot]:
        if not candles:
            raise ValueError("Candles dataset is empty.")

        validation_errors = validate_candle_dataset(candles)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        closes = [float(candle.close) for candle in candles]
        ema_fast = calculate_ema(closes, self.config.ema_fast)
        ema_slow = calculate_ema(closes, self.config.ema_slow)
        rsi_values = calculate_rsi(closes, self.config.rsi_period)
        macd_result = calculate_macd(closes, self.config.macd_fast, self.config.macd_slow, self.config.macd_signal)

        snapshots: list[IndicatorSnapshot] = []
        for index, candle in enumerate(candles):
            snapshots.append(
                IndicatorSnapshot(
                    timestamp=candle.timestamp,
                    symbol=candle.symbol,
                    timeframe=candle.timeframe,
                    close=candle.close,
                    ema_fast=ema_fast[index],
                    ema_slow=ema_slow[index],
                    rsi=rsi_values[index],
                    macd=macd_result.macd[index],
                    macd_signal=macd_result.signal[index],
                    macd_histogram=macd_result.histogram[index],
                )
            )

        return snapshots
