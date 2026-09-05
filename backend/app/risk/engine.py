"""Placeholder risk engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskProfile:
    level: str
    exposure: float
    max_drawdown: float


class RiskEngine:
    """Evaluates portfolio risk while keeping decision-making conservative."""

    def evaluate(self, score: int) -> RiskProfile:
        if score >= 65:
            return RiskProfile(level="Moderate", exposure=0.3, max_drawdown=0.12)
        if score <= 35:
            return RiskProfile(level="High", exposure=0.5, max_drawdown=0.2)
        return RiskProfile(level="Balanced", exposure=0.2, max_drawdown=0.08)
