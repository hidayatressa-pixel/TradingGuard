"""Placeholder backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BacktestResult:
    net_return: float
    win_rate: float
    benchmark: str


class BacktestEngine:
    """Runs a historical simulation without live order execution."""

    def run(self) -> BacktestResult:
        return BacktestResult(
            net_return=0.08,
            win_rate=0.55,
            benchmark="buy-and-hold",
        )
