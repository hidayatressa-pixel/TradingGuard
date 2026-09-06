from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class RiskSizingRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    equity: float
    entry_price: float
    stop_loss_price: float
    risk_budget_pct: float
    max_allocation_pct: float | None = None

    @field_validator("equity", "entry_price", "stop_loss_price", "risk_budget_pct", "max_allocation_pct")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("risk sizing numeric values must be finite.")
        return value

    @model_validator(mode="after")
    def validate_request(self) -> "RiskSizingRequest":
        if self.equity <= 0:
            raise ValueError("equity must be greater than zero.")
        if self.entry_price <= 0:
            raise ValueError("entry_price must be greater than zero.")
        if self.stop_loss_price <= 0:
            raise ValueError("stop_loss_price must be greater than zero.")
        if self.stop_loss_price >= self.entry_price:
            raise ValueError("stop_loss_price must be below entry_price for a long position.")
        if self.risk_budget_pct <= 0:
            raise ValueError("risk_budget_pct must be greater than zero.")
        if self.max_allocation_pct is not None and not 0 < self.max_allocation_pct <= 100:
            raise ValueError("max_allocation_pct must be between 0 and 100 when supplied.")
        return self


class RiskSizingResult(BaseModel):
    model_config = ConfigDict(strict=True)

    equity: float
    entry_price: float
    stop_loss_price: float
    stop_distance: float
    stop_distance_pct: float
    requested_risk_budget_pct: float
    requested_risk_budget_amount: float
    max_allocation_pct: float | None
    quantity_by_risk: float
    notional_by_risk: float
    final_quantity: float
    final_notional: float
    risk_amount: float
    risk_per_trade_pct: float
    allocation_pct: float
    allocation_cap_applied: bool
    costs_included_in_risk: bool = False
    cost_treatment: str = "Price risk to stop only; transaction costs and slippage are not included."
