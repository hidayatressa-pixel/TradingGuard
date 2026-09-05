"""Placeholder signal scoring implementation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SignalScore:
    score: int
    label: str
    confidence: float


class SignalScorer:
    """Generates a non-deterministic trading signal from technical inputs."""

    def score(self, rsi: float, trend_bias: str) -> SignalScore:
        raw_score = 50 + int((rsi - 50) * 0.5)
        if trend_bias == "bullish":
            raw_score += 10
        elif trend_bias == "bearish":
            raw_score -= 10

        if raw_score >= 60:
            return SignalScore(score=raw_score, label="Bullish", confidence=0.72)
        if raw_score <= 40:
            return SignalScore(score=raw_score, label="Bearish", confidence=0.68)
        return SignalScore(score=raw_score, label="Neutral", confidence=0.6)
