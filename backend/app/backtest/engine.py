"""Deterministic backtesting engine for TradingGuard."""

from __future__ import annotations

from backend.app.market.models import Candle
from backend.app.strategy.models import StrategyResult

from .models import BacktestConfig, BacktestResult
from .service import BacktestService


class BacktestEngine:
    """Compatibility wrapper around the V0.6 historical evaluation service."""

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()
        self.service = BacktestService()

    def run(self, candles: list[Candle], strategy_results: list[StrategyResult]) -> BacktestResult:
        return self.service.evaluate(candles, strategy_results, self.config)
