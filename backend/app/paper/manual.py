from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.app.market.models import Candle
from backend.app.paper.models import PaperAccount
from backend.app.paper.portfolio import PaperPortfolioService
from backend.app.paper.service import PaperTradingService
from backend.app.risk.integration import ProspectiveRiskGateResult, ProspectiveRiskGateService
from backend.app.risk.models import RiskDecision
from backend.app.risk_sizing.auto_stop import AutoStopLossResult, AutoStopLossService
from backend.app.risk_sizing.models import RiskSizingRequest
from backend.app.strategy.models import Assessment, StrategyResult


class ManualGuardedTradeResult(BaseModel):
    model_config = ConfigDict(strict=True)
    action: Literal["BUY", "SELL"]
    executed: bool
    decision: str
    strategy: StrategyResult
    gate: ProspectiveRiskGateResult | None = None
    auto_stop: AutoStopLossResult | None = None
    execution_price: float | None = None
    reason: str
    account: PaperAccount


class ManualGuardedTradeService:
    """Interactive multi-symbol PAPER decision tester."""

    def __init__(self, paper_service: PaperTradingService) -> None:
        self.paper_service = paper_service
        self.portfolio_service = PaperPortfolioService(paper_service)
        self.stop_service = AutoStopLossService()
        self.gate_service = ProspectiveRiskGateService()

    def buy(self, *, completed_candles: list[Candle], strategy: StrategyResult,
            market_price: float, risk_budget_pct: float = 0.5,
            max_allocation_pct: float = 20.0) -> ManualGuardedTradeResult:
        account = self.paper_service.state()
        if not account.active or not account.config.paper_trading_enabled:
            return self._result("BUY", False, "BLOCK", strategy, account, reason="Paper account is inactive.")
        if account.position_for(strategy.symbol) is not None:
            return self._result("BUY", False, "BLOCK", strategy, account, reason=f"Position {strategy.symbol} is already open; duplicate symbol exposure is not allowed.")
        if account.pending_entry is not None or account.pending_exit is not None:
            return self._result("BUY", False, "BLOCK", strategy, account, reason="A legacy paper action is pending; complete/cancel it before a manual portfolio entry.")
        if not strategy.data_ready:
            return self._result("BUY", False, "BLOCK", strategy, account, reason="Strategy data is not ready.")
        if strategy.assessment not in {Assessment.BULLISH, Assessment.STRONG_BULLISH}:
            return self._result("BUY", False, "BLOCK", strategy, account, reason=f"Manual BUY rejected: market condition is {strategy.assessment.value}, not BULLISH/STRONG_BULLISH.")

        self.paper_service.prepare_risk_day(strategy.timestamp)
        stop = self.stop_service.evaluate(completed_candles, market_price)
        if not stop.valid or stop.stop_loss_price is None:
            return self._result("BUY", False, "BLOCK", strategy, account, auto_stop=stop, reason=f"Auto Stop rejected BUY: {stop.reason}")

        sizing = RiskSizingRequest(equity=float(account.realized_equity), entry_price=float(market_price), stop_loss_price=float(stop.stop_loss_price), risk_budget_pct=float(risk_budget_pct), max_allocation_pct=float(max_allocation_pct))
        gate = self.gate_service.evaluate(strategy, account, sizing)
        decision = gate.risk.decision.value if gate.risk is not None else "BLOCK"
        if not gate.execution_permission_established or gate.risk is None or gate.risk.decision != RiskDecision.ALLOW:
            return self._result("BUY", False, decision, strategy, account, gate=gate, auto_stop=stop, reason=gate.reason)

        account = self.portfolio_service.buy(strategy=strategy, risk=gate.risk, quantity=gate.sizing.final_quantity, stop_loss_price=gate.sizing.stop_loss_price, execution_price=float(market_price), timestamp=datetime.now(timezone.utc))
        position=account.position_for(strategy.symbol)
        return self._result("BUY", True, "ALLOW", strategy, account, gate=gate, auto_stop=stop, execution_price=float(position.entry_price) if position else None, reason=f"Manual PAPER BUY {strategy.symbol} executed after Auto Stop + Risk Sizing + aggregate portfolio Risk Guard ALLOW.")

    def sell(self, *, strategy: StrategyResult, market_price: float, symbol: str | None = None) -> ManualGuardedTradeResult:
        account = self.paper_service.state(); target=symbol or strategy.symbol
        if not account.active or account.position_for(target) is None:
            return self._result("SELL", False, "BLOCK", strategy, account, reason=f"No active paper position for {target} to SELL.")
        account = self.portfolio_service.sell(symbol=target, execution_price=float(market_price), timestamp=datetime.now(timezone.utc))
        return self._result("SELL", True, "REDUCE_RISK", strategy, account, execution_price=float(market_price), reason=f"Manual PAPER SELL {target} executed; closing exposure does not require Risk Guard ALLOW.")

    @staticmethod
    def _result(action: Literal["BUY", "SELL"], executed: bool, decision: str, strategy: StrategyResult, account: PaperAccount, *, gate: ProspectiveRiskGateResult | None = None, auto_stop: AutoStopLossResult | None = None, execution_price: float | None = None, reason: str) -> ManualGuardedTradeResult:
        return ManualGuardedTradeResult(action=action, executed=executed, decision=decision, strategy=strategy, gate=gate, auto_stop=auto_stop, execution_price=execution_price, reason=reason, account=account)
