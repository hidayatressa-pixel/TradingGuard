"""Placeholder market data access layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    change_pct: float
    volume: int


class MarketDataProvider:
    """Returns market snapshots for the strategy layer in a testable way."""

    def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=symbol,
            price=100.0,
            change_pct=0.8,
            volume=500000,
        )
