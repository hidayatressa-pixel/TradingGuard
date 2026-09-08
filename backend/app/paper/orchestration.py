from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.market.models import Candle
from backend.app.paper.service import PaperTradingService
from backend.app.risk.integration import ProspectiveRiskGateResult, ProspectiveRiskGateService
from backend.app.risk.models import RiskPolicy
from backend.app.risk_sizing.auto_stop import AutoStopLossResult, AutoStopLossService
from backend.app.risk_sizing.models import RiskSizingRequest
from backend.app.strategy.models import Assessment, StrategyResult


class AutoPaperEntryResult(BaseModel):
    model_config = ConfigDict(strict=True)
    scheduled: bool
    execution_permission_established: bool
    gate: ProspectiveRiskGateResult | None = None
    auto_stop: AutoStopLossResult | None = None
    reason: str


class AutoPaperEntryOrchestrator:
    """Backend-owned PAPER entry interlock; never executes an entry immediately."""

    def __init__(self, paper_service: PaperTradingService) -> None:
        self.paper_service = paper_service
        self.gate_service = ProspectiveRiskGateService()
        self.auto_stop_service = AutoStopLossService()

    def evaluate_and_schedule(self, *, strategy: StrategyResult, reference_entry_price: float,
                              stop_loss_price: float, risk_budget_pct: float,
                              max_allocation_pct: float | None = None,
                              policy: RiskPolicy | None = None) -> AutoPaperEntryResult:
        """Manual/testing path retained for compatibility."""
        return self._evaluate(strategy=strategy, reference_entry_price=reference_entry_price,
                              stop_loss_price=stop_loss_price, risk_budget_pct=risk_budget_pct,
                              max_allocation_pct=max_allocation_pct, policy=policy, auto_stop=None)

    def evaluate_and_schedule_auto(self, *, strategy: StrategyResult, candles: list[Candle],
                                   risk_budget_pct: float,
                                   max_allocation_pct: float | None = None,
                                   policy: RiskPolicy | None = None) -> AutoPaperEntryResult:
        """Autonomous path: market data owns entry reference and stop derivation."""
        if not candles:
            return AutoPaperEntryResult(scheduled=False, execution_permission_established=False,
                                        reason="No authoritative candle data; auto entry remains fail-closed.")
        reference_entry_price = float(candles[-1].close)
        auto_stop = self.auto_stop_service.evaluate(candles, reference_entry_price)
        if not auto_stop.valid or auto_stop.stop_loss_price is None:
            return AutoPaperEntryResult(scheduled=False, execution_permission_established=False,
                                        auto_stop=auto_stop,
                                        reason=f"Automatic stop interlock blocked entry: {auto_stop.reason}")
        return self._evaluate(strategy=strategy, reference_entry_price=reference_entry_price,
                              stop_loss_price=auto_stop.stop_loss_price, risk_budget_pct=risk_budget_pct,
                              max_allocation_pct=max_allocation_pct, policy=policy, auto_stop=auto_stop)

    def _evaluate(self, *, strategy: StrategyResult, reference_entry_price: float,
                  stop_loss_price: float, risk_budget_pct: float,
                  max_allocation_pct: float | None, policy: RiskPolicy | None,
                  auto_stop: AutoStopLossResult | None) -> AutoPaperEntryResult:
        account = self.paper_service.state()
        if not account.active or not account.config.paper_trading_enabled:
            return AutoPaperEntryResult(scheduled=False, execution_permission_established=False,
                                        auto_stop=auto_stop, reason="Paper trading is inactive; no BUY was scheduled.")
        if account.open_position is not None or account.pending_entry is not None or account.pending_exit is not None:
            return AutoPaperEntryResult(scheduled=False, execution_permission_established=False,
                                        auto_stop=auto_stop, reason="Paper account is not flat; no new BUY was scheduled.")
        if not strategy.data_ready or strategy.assessment not in {Assessment.BULLISH, Assessment.STRONG_BULLISH}:
            return AutoPaperEntryResult(scheduled=False, execution_permission_established=False,
                                        auto_stop=auto_stop, reason="Current strategy is not an eligible bullish entry condition.")
        sizing_request = RiskSizingRequest(equity=float(account.realized_equity),
            entry_price=float(reference_entry_price), stop_loss_price=float(stop_loss_price),
            risk_budget_pct=float(risk_budget_pct),
            max_allocation_pct=None if max_allocation_pct is None else float(max_allocation_pct))
        gate = self.gate_service.evaluate(strategy, account, sizing_request, policy)
        if not gate.execution_permission_established or gate.risk is None:
            return AutoPaperEntryResult(scheduled=False, execution_permission_established=False,
                                        gate=gate, auto_stop=auto_stop, reason=gate.reason)
        self.paper_service.schedule_sized_entry(strategy=strategy, risk=gate.risk,
            quantity=gate.sizing.final_quantity, stop_loss_price=gate.sizing.stop_loss_price,
            expected_equity=gate.sizing.equity)
        return AutoPaperEntryResult(scheduled=True, execution_permission_established=True,
                                    gate=gate, auto_stop=auto_stop,
                                    reason="All entry interlocks passed; sized PAPER BUY is scheduled for next-event revalidation.")
