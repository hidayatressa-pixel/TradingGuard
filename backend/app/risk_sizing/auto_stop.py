from __future__ import annotations

from math import isfinite

from pydantic import BaseModel, ConfigDict

from backend.app.market.models import Candle


class AutoStopLossResult(BaseModel):
    """Backend-owned long stop proposal derived only from completed OHLC candles."""

    model_config = ConfigDict(strict=True)

    valid: bool
    stop_loss_price: float | None = None
    method: str
    atr: float | None = None
    structure_low: float | None = None
    stop_distance_pct: float | None = None
    reason: str


class AutoStopLossService:
    """Conservative structure + ATR stop engine.

    This service never loosens a stop merely to obtain Risk Guard ALLOW. If the
    market data cannot establish a bounded stop below entry, it fails closed.
    """

    def __init__(self, *, atr_period: int = 14, structure_lookback: int = 10, atr_buffer: float = 0.5) -> None:
        if atr_period < 2 or structure_lookback < 2 or atr_buffer <= 0:
            raise ValueError("Auto stop configuration must be positive and use lookbacks >= 2.")
        self.atr_period = atr_period
        self.structure_lookback = structure_lookback
        self.atr_buffer = atr_buffer

    def evaluate(self, candles: list[Candle], entry_price: float) -> AutoStopLossResult:
        if not isfinite(entry_price) or entry_price <= 0:
            return self._invalid("Reference entry price is not finite and positive.")
        minimum = max(self.atr_period + 1, self.structure_lookback)
        if len(candles) < minimum:
            return self._invalid(f"At least {minimum} completed candles are required for automatic stop loss.")
        symbol, timeframe = candles[-1].symbol, candles[-1].timeframe
        if any(c.symbol != symbol or c.timeframe != timeframe for c in candles[-minimum:]):
            return self._invalid("Candle symbol/timeframe alignment is invalid.")

        trs: list[float] = []
        for index in range(len(candles) - self.atr_period, len(candles)):
            candle = candles[index]
            previous_close = candles[index - 1].close
            trs.append(max(candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close)))
        atr = sum(trs) / len(trs)
        if not isfinite(atr) or atr <= 0:
            return self._invalid("ATR is unavailable or non-positive.")

        structure_low = min(c.low for c in candles[-self.structure_lookback:])
        # Place the stop below recent structure with a volatility buffer. This is
        # intentionally independent from the risk budget; sizing adapts to stop,
        # never the other way around.
        stop = structure_low - (atr * self.atr_buffer)
        if not isfinite(stop) or stop <= 0 or stop >= entry_price:
            return self._invalid("Recent structure does not produce a valid long stop below entry.")
        distance_pct = ((entry_price - stop) / entry_price) * 100.0
        if not isfinite(distance_pct) or distance_pct <= 0:
            return self._invalid("Automatic stop distance is invalid.")
        return AutoStopLossResult(
            valid=True,
            stop_loss_price=float(stop),
            method="STRUCTURE_LOW_PLUS_ATR_BUFFER",
            atr=float(atr),
            structure_low=float(structure_low),
            stop_distance_pct=float(distance_pct),
            reason="Stop derived from recent structure low with ATR volatility buffer.",
        )

    @staticmethod
    def _invalid(reason: str) -> AutoStopLossResult:
        return AutoStopLossResult(valid=False, method="UNAVAILABLE", reason=reason)
