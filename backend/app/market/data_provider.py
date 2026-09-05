"""Market data provider interfaces and deterministic mock implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Final

from .models import Candle


class MarketDataProvider(ABC):
    """Provider-agnostic interface for retrieving normalized OHLCV candles."""

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        """Return a time-ordered list of candles for the requested market."""


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic mock provider for local development and automated tests."""

    VALID_TIMEFRAMES: Final[dict[str, timedelta]] = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1d": timedelta(days=1),
    }

    def __init__(self, symbol: str = "BTCUSD", timeframe: str = "1h", candle_count: int = 100) -> None:
        self.symbol = symbol.strip().upper()
        self.timeframe = timeframe.strip().lower()
        self.candle_count = max(1, int(candle_count))

    def _resolve_timeframe(self, timeframe: str) -> timedelta:
        normalized = timeframe.strip().lower()
        if normalized not in self.VALID_TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return self.VALID_TIMEFRAMES[normalized]

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        normalized_symbol = symbol.strip().upper()
        normalized_timeframe = timeframe.strip().lower()
        candle_limit = max(1, min(int(limit), 500))

        interval = self._resolve_timeframe(normalized_timeframe)
        base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        seed = sum(ord(char) for char in normalized_symbol)

        candles: list[Candle] = []
        for index in range(candle_limit):
            timestamp = base_timestamp + index * interval
            wave = 0.7 * (index % 9)
            drift = (index % 5) * 0.35
            open_price = 100.0 + wave + drift + (seed % 7) * 0.12
            close_price = open_price + ((index % 3) - 1) * 1.75 + ((seed % 11) * 0.07)
            high_price = max(open_price, close_price) + 1.5 + ((index % 4) * 0.5)
            low_price = min(open_price, close_price) - 1.2 - ((index % 5) * 0.4)
            volume = 1500.0 + index * 27.5 + (seed % 19) * 10.0

            candle = Candle(
                timestamp=timestamp,
                symbol=normalized_symbol,
                timeframe=normalized_timeframe,
                open=round(open_price, 4),
                high=round(high_price, 4),
                low=round(low_price, 4),
                close=round(close_price, 4),
                volume=round(volume, 2),
            )
            candles.append(candle)

        return candles
