from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from backend.app.paper.models import PaperAccount
from backend.app.risk.models import RiskContext


class RiskContextAvailability(BaseModel):
    model_config = ConfigDict(strict=True)
    available: bool
    context: RiskContext | None = None
    missing_facts: list[str]
    reason: str


class PaperRiskContextBuilder:
    """Build prospective-entry RiskContext only from authoritative paper portfolio state."""

    def build(self, account: PaperAccount, risk_per_trade_pct: float | None) -> RiskContextAvailability:
        missing: list[str] = []
        if risk_per_trade_pct is None or not math.isfinite(risk_per_trade_pct) or risk_per_trade_pct < 0:
            missing.append("risk_per_trade_pct")
        if account.risk_day is None:
            missing.append("risk_day")
        if not math.isfinite(account.day_start_equity) or account.day_start_equity <= 0:
            missing.append("day_start_equity")
        if not math.isfinite(account.peak_realized_equity) or account.peak_realized_equity <= 0:
            missing.append("peak_realized_equity")
        if missing:
            return RiskContextAvailability(available=False, context=None, missing_facts=missing, reason="Complete authoritative RiskContext is unavailable; prospective entry remains fail-closed.")

        daily_loss_pct = max((account.day_start_equity - account.realized_equity) / account.day_start_equity * 100.0, 0.0)
        drawdown_pct = max((account.peak_realized_equity - account.realized_equity) / account.peak_realized_equity * 100.0, 0.0)
        positions=account.open_positions if account.open_positions else ([account.open_position] if account.open_position is not None else [])
        exposure_notional=sum(position.entry_notional for position in positions)
        total_exposure_pct = (exposure_notional / account.realized_equity * 100.0) if account.realized_equity > 0 else math.inf
        values = (daily_loss_pct, drawdown_pct, total_exposure_pct)
        if not all(math.isfinite(value) and value >= 0 for value in values):
            return RiskContextAvailability(available=False, context=None, missing_facts=["derived_account_risk"], reason="Derived account risk is invalid; prospective entry remains fail-closed.")

        context = RiskContext(risk_per_trade_pct=float(risk_per_trade_pct), daily_loss_pct=daily_loss_pct, total_exposure_pct=total_exposure_pct, open_positions=len(positions), current_drawdown_pct=drawdown_pct, trading_enabled=account.active and account.config.paper_trading_enabled)
        return RiskContextAvailability(available=True, context=context, missing_facts=[], reason="Complete authoritative paper portfolio RiskContext is available for Risk Guard evaluation.")
