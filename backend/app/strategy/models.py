from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class Assessment(str, Enum):
    STRONG_BEARISH = "STRONG_BEARISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    BULLISH = "BULLISH"
    STRONG_BULLISH = "STRONG_BULLISH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class StrategyEvidence(BaseModel):
    model_config = ConfigDict(strict=True)

    indicator: str
    condition: str
    contribution: int
    description: str


class StrategyResult(BaseModel):
    model_config = ConfigDict(strict=True)

    timestamp: datetime
    symbol: str
    timeframe: str
    score: int
    normalized_score: int
    assessment: Assessment
    data_ready: bool
    evidence: list[StrategyEvidence]
