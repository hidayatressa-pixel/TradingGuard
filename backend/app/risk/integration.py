from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.paper.models import PaperAccount
from backend.app.risk.context import PaperRiskContextBuilder, RiskContextAvailability
from backend.app.risk.models import RiskPolicy, RiskResult
from backend.app.risk.service import RiskService
from backend.app.risk_sizing.models import RiskSizingRequest, RiskSizingResult
from backend.app.risk_sizing.service import RiskSizingService
from backend.app.strategy.models import StrategyResult


class ProspectiveRiskGateResult(BaseModel):
    model_config = ConfigDict(strict=True)

    sizing: RiskSizingResult
    context_availability: RiskContextAvailability
    risk: RiskResult | None = None
    execution_permission_established: bool
    reason: str


class ProspectiveRiskGateService:
    """Orchestrate sizing -> authoritative context -> Risk Guard without executing trades."""

    def __init__(self) -> None:
        self.sizing_service = RiskSizingService()
        self.context_builder = PaperRiskContextBuilder()
        self.risk_service = RiskService()

    def evaluate(
        self,
        strategy: StrategyResult,
        account: PaperAccount,
        sizing_request: RiskSizingRequest,
        policy: RiskPolicy | None = None,
    ) -> ProspectiveRiskGateResult:
        sizing = self.sizing_service.evaluate(sizing_request)
        context_availability = self.context_builder.build(account, sizing.risk_per_trade_pct)

        if not context_availability.available or context_availability.context is None:
            return ProspectiveRiskGateResult(
                sizing=sizing,
                context_availability=context_availability,
                risk=None,
                execution_permission_established=False,
                reason="Risk Guard was not evaluated because complete authoritative RiskContext is unavailable.",
            )

        risk = self.risk_service.evaluate(strategy, context_availability.context, policy or RiskPolicy())
        return ProspectiveRiskGateResult(
            sizing=sizing,
            context_availability=context_availability,
            risk=risk,
            execution_permission_established=risk.decision.value == "ALLOW",
            reason=(
                "Risk Guard established ALLOW for this prospective entry."
                if risk.decision.value == "ALLOW"
                else f"Risk Guard decision is {risk.decision.value}; prospective entry is not authorized."
            ),
        )
