"""Market data provider interfaces, deterministic mock data, and public real market data."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Candle


class MarketDataProvider(ABC):
    """Provider-agnostic interface for retrieving normalized OHLCV candles."""

    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]:
        """Return a time-ordered list of candles for the requested market."""


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic mock provider for local development and automated tests."""

    VALID_TIMEFRAMES: Final[dict[str, timedelta]] = {
        "1m": timedelta(minutes=1), "5m": timedelta(minutes=5), "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1), "4h": timedelta(hours=4), "1d": timedelta(days=1),
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

    def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]:
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
            candles.append(Candle(timestamp=timestamp, symbol=normalized_symbol, timeframe=normalized_timeframe,
                                  open=round(open_price, 4), high=round(high_price, 4), low=round(low_price, 4),
                                  close=round(close_price, 4), volume=round(volume, 2)))
        return candles


class BinancePublicMarketDataProvider(MarketDataProvider):
    """Read-only Binance public spot market-data provider. No API key or trading endpoint is used."""

    BASE_URL: Final[str] = "https://data-api.binance.vision/api/v3/klines"
    VALID_TIMEFRAMES: Final[set[str]] = {"1m", "5m", "15m", "1h", "4h", "1d"}

    def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]:
        normalized_symbol = symbol.strip().upper()
        normalized_timeframe = timeframe.strip().lower()
        if not normalized_symbol:
            raise ValueError("Symbol is required.")
        if normalized_timeframe not in self.VALID_TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        candle_limit = max(1, min(int(limit), 500))
        url = f"{self.BASE_URL}?{urlencode({'symbol': normalized_symbol, 'interval': normalized_timeframe, 'limit': candle_limit})}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "TradingGuard/0.8"})
        try:
            with urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ValueError(f"Real market provider rejected the request: {detail}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("Real market provider is temporarily unavailable.") from exc

        if not isinstance(payload, list):
            raise RuntimeError("Real market provider returned an unexpected response.")

        candles: list[Candle] = []
        try:
            for row in payload:
                candles.append(Candle(
                    timestamp=datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc),
                    symbol=normalized_symbol,
                    timeframe=normalized_timeframe,
                    open=float(row[1]), high=float(row[2]), low=float(row[3]), close=float(row[4]), volume=float(row[5]),
                ))
        except (IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Real market provider returned malformed candle data.") from exc
        return candles
