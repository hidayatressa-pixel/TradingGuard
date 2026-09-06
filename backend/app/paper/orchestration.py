from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.paper.models import PaperAccount
from backend.app.paper.service import PaperTradingService
from backend.app.risk.integration import ProspectiveRiskGateResult, ProspectiveRiskGateService
from backend.app.risk.models import RiskPolicy
from backend.app.risk_sizing.models import RiskSizingRequest
from backend.app.strategy.models import Assessment, StrategyResult


class AutoPaperEntryResult(BaseModel):
    model_config = ConfigDict(strict=True)

    scheduled: bool
    execution_permission_established: bool
    gate: ProspectiveRiskGateResult | None = None
    reason: str


class AutoPaperEntryOrchestrator:
    """Backend-owned prospective PAPER entry orchestration; never executes immediately."""

    def __init__(self, paper_service: PaperTradingService) -> None:
        self.paper_service = paper_service
        self.gate_service = ProspectiveRiskGateService()

    def evaluate_and_schedule(
        self,
        *,
        strategy: StrategyResult,
        reference_entry_price: float,
        stop_loss_price: float,
        risk_budget_pct: float,
        max_allocation_pct: float | None = None,
        policy: RiskPolicy | None = None,
    ) -> AutoPaperEntryResult:
        account = self.paper_service.state()

        if not account.active or not account.config.paper_trading_enabled:
            return AutoPaperEntryResult(
                scheduled=False,
                execution_permission_established=False,
                reason="Paper trading is inactive; no BUY was scheduled.",
            )
        if account.open_position is not None or account.pending_entry is not None or account.pending_exit is not None:
            return AutoPaperEntryResult(
                scheduled=False,
                execution_permission_established=False,
                reason="Paper account is not flat; no new BUY was scheduled.",
            )
        if not strategy.data_ready or strategy.assessment not in {Assessment.BULLISH, Assessment.STRONG_BULLISH}:
            return AutoPaperEntryResult(
                scheduled=False,
                execution_permission_established=False,
                reason="Current strategy is not an eligible bullish entry condition.",
            )

        sizing_request = RiskSizingRequest(
            equity=float(account.realized_equity),
            entry_price=float(reference_entry_price),
            stop_loss_price=float(stop_loss_price),
            risk_budget_pct=float(risk_budget_pct),
            max_allocation_pct=None if max_allocation_pct is None else float(max_allocation_pct),
        )
        gate = self.gate_service.evaluate(strategy, account, sizing_request, policy)
        if not gate.execution_permission_established or gate.risk is None:
            return AutoPaperEntryResult(
                scheduled=False,
                execution_permission_established=False,
                gate=gate,
                reason=gate.reason,
            )

        # Bind exactly the authoritative sizing output. No allocation-based fallback or quantity recomputation.
        self.paper_service.schedule_sized_entry(
            strategy=strategy,
            risk=gate.risk,
            quantity=gate.sizing.final_quantity,
            stop_loss_price=gate.sizing.stop_loss_price,
            expected_equity=gate.sizing.equity,
        )
        return AutoPaperEntryResult(
            scheduled=True,
            execution_permission_established=True,
            gate=gate,
            reason="Risk Guard ALLOW established; authoritative sized PAPER BUY is scheduled for next-event execution revalidation.",
        )
