from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RiskDecision(str, Enum):
    ALLOW = "ALLOW"
    WARNING = "WARNING"
    BLOCK = "BLOCK"


class RiskStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    BLOCK = "BLOCK"


class RiskEvidence(BaseModel):
    model_config = ConfigDict()

    rule: str
    status: RiskStatus
    value: float | int | bool
    threshold: float | int | bool | None = None
    description: str


class RiskPolicy(BaseModel):
    model_config = ConfigDict()

    max_risk_per_trade_pct: float = 1.0
    warning_risk_per_trade_pct: float = 0.75

    max_daily_loss_pct: float = 3.0
    warning_daily_loss_pct: float = 2.0

    max_total_exposure_pct: float = 20.0
    warning_total_exposure_pct: float = 15.0

    max_open_positions: int = 3
    warning_open_positions: int = 2

    max_drawdown_pct: float = 10.0
    warning_drawdown_pct: float = 7.5

    @model_validator(mode="after")
    def validate_policy(self) -> "RiskPolicy":
        if self.warning_risk_per_trade_pct < 0 or self.warning_risk_per_trade_pct > self.max_risk_per_trade_pct:
            raise ValueError("warning_risk_per_trade_pct must be between 0 and max_risk_per_trade_pct")
        if self.warning_daily_loss_pct < 0 or self.warning_daily_loss_pct > self.max_daily_loss_pct:
            raise ValueError("warning_daily_loss_pct must be between 0 and max_daily_loss_pct")
        if self.warning_total_exposure_pct < 0 or self.warning_total_exposure_pct > self.max_total_exposure_pct:
            raise ValueError("warning_total_exposure_pct must be between 0 and max_total_exposure_pct")
        if self.warning_open_positions < 0 or self.warning_open_positions > self.max_open_positions:
            raise ValueError("warning_open_positions must be between 0 and max_open_positions")
        if self.warning_drawdown_pct < 0 or self.warning_drawdown_pct > self.max_drawdown_pct:
            raise ValueError("warning_drawdown_pct must be between 0 and max_drawdown_pct")

        if self.max_risk_per_trade_pct <= 0:
            raise ValueError("max_risk_per_trade_pct must be positive")
        if self.max_daily_loss_pct <= 0:
            raise ValueError("max_daily_loss_pct must be positive")
        if self.max_total_exposure_pct <= 0:
            raise ValueError("max_total_exposure_pct must be positive")
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be positive")
        if self.max_drawdown_pct <= 0:
            raise ValueError("max_drawdown_pct must be positive")

        return self


class RiskContext(BaseModel):
    model_config = ConfigDict()

    risk_per_trade_pct: float
    daily_loss_pct: float
    total_exposure_pct: float
    open_positions: int
    current_drawdown_pct: float
    trading_enabled: bool = True

    @model_validator(mode="after")
    def validate_context(self) -> "RiskContext":
        if self.risk_per_trade_pct < 0:
            raise ValueError("risk_per_trade_pct must be non-negative")
        if self.daily_loss_pct < 0:
            raise ValueError("daily_loss_pct must be non-negative")
        if self.total_exposure_pct < 0:
            raise ValueError("total_exposure_pct must be non-negative")
        if self.open_positions < 0:
            raise ValueError("open_positions must be non-negative")
        if self.current_drawdown_pct < 0:
            raise ValueError("current_drawdown_pct must be non-negative")
        return self


class RiskResult(BaseModel):
    model_config = ConfigDict()

    timestamp: datetime
    symbol: str
    timeframe: str
    strategy_assessment: str
    strategy_score: int
    decision: RiskDecision
    data_ready: bool
    evidence: list[RiskEvidence]
    block_reasons: list[str]
    warning_reasons: list[str]
