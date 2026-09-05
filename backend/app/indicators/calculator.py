"""Placeholder technical indicator calculations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IndicatorSummary:
    rsi: float
    moving_average: float
    trend_bias: str


class IndicatorCalculator:
    """Represents a thin, modular interface for technical analysis."""

    def calculate(self, price: float) -> IndicatorSummary:
        return IndicatorSummary(
            rsi=56.0,
            moving_average=price,
            trend_bias="neutral",
        )
