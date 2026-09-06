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
    """Build only risk facts that are authoritative from current paper state.

    V0.7 does not retain day-start or peak-equity baselines, so daily loss and
    drawdown must remain unavailable rather than being fabricated as zero.
    """

    def build(self, account: PaperAccount, risk_per_trade_pct: float | None) -> RiskContextAvailability:
        missing: list[str] = []
        if risk_per_trade_pct is None or not math.isfinite(risk_per_trade_pct) or risk_per_trade_pct < 0:
            missing.append("risk_per_trade_pct")

        # These cannot be derived truthfully from committed V0.7 PaperAccount.
        missing.extend(["daily_loss_pct", "current_drawdown_pct"])

        if missing:
            return RiskContextAvailability(
                available=False,
                context=None,
                missing_facts=missing,
                reason="Complete authoritative RiskContext is unavailable; prospective entry remains fail-closed.",
            )

        # Kept unreachable until authoritative baselines are introduced.
        raise RuntimeError("RiskContext builder requires authoritative daily-loss and drawdown baselines.")
