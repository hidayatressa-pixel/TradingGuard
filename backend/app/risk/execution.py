from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from backend.app.market.models import Candle
from backend.app.paper.models import PaperAccount, PendingEntry
from backend.app.risk.context import PaperRiskContextBuilder, RiskContextAvailability
from backend.app.risk.models import RiskDecision, RiskPolicy, RiskResult
from backend.app.risk.service import RiskService
from backend.app.strategy.models import StrategyResult


class ExecutionRiskEstimate(BaseModel):
    model_config = ConfigDict(strict=True)

    effective_entry_price: float
    estimated_stop_fill_price: float
    quantity: float
    price_loss: float
    entry_fee: float
    estimated_exit_fee: float
    planned_all_in_loss: float
    risk_per_trade_pct: float


class ExecutionRevalidationResult(BaseModel):
    model_config = ConfigDict(strict=True)

    allowed: bool
    estimate: ExecutionRiskEstimate | None = None
    context_availability: RiskContextAvailability | None = None
    risk: RiskResult | None = None
    reason: str


class ExecutionRiskRevalidationService:
    """Revalidate an already-sized Paper entry at the actual next candle OPEN."""

    def __init__(self) -> None:
        self.context_builder = PaperRiskContextBuilder()
        self.risk_service = RiskService()

    def evaluate(
        self,
        *,
        account: PaperAccount,
        candle: Candle,
        strategy: StrategyResult,
        pending: PendingEntry,
        policy: RiskPolicy | None = None,
    ) -> ExecutionRevalidationResult:
        if pending.quantity is None or pending.stop_loss_price is None:
            return ExecutionRevalidationResult(allowed=False, reason="Sized quantity and stop-loss are required for execution revalidation.")
        if candle.symbol != pending.symbol or candle.timeframe != pending.timeframe:
            return ExecutionRevalidationResult(allowed=False, reason="Execution candle does not match the pending entry instrument.")
        if not account.active or not account.config.paper_trading_enabled:
            return ExecutionRevalidationResult(allowed=False, reason="Paper trading is disabled; execution remains fail-closed.")
        if not math.isfinite(account.realized_equity) or account.realized_equity <= 0:
            return ExecutionRevalidationResult(allowed=False, reason="Authoritative Paper equity is invalid.")

        q = float(pending.quantity)
        stop = float(pending.stop_loss_price)
        entry_slippage = account.config.slippage_pct / 100.0
        exit_slippage = account.config.slippage_pct / 100.0
        fee_rate = account.config.transaction_cost_pct / 100.0
        effective_entry = float(candle.open) * (1.0 + entry_slippage)
        estimated_stop_fill = stop * (1.0 - exit_slippage)

        numeric = (q, stop, effective_entry, estimated_stop_fill, fee_rate, entry_slippage, exit_slippage)
        if not all(math.isfinite(value) for value in numeric) or q <= 0 or stop <= 0 or effective_entry <= 0 or estimated_stop_fill <= 0:
            return ExecutionRevalidationResult(allowed=False, reason="Execution risk inputs are invalid or non-finite.")
        if stop >= effective_entry:
            return ExecutionRevalidationResult(allowed=False, reason="Stop-loss is no longer below the effective long entry price.")

        price_loss = q * (effective_entry - estimated_stop_fill)
        entry_fee = q * effective_entry * fee_rate
        estimated_exit_fee = q * estimated_stop_fill * fee_rate
        planned_all_in_loss = price_loss + entry_fee + estimated_exit_fee
        risk_per_trade_pct = planned_all_in_loss / account.realized_equity * 100.0
        derived = (price_loss, entry_fee, estimated_exit_fee, planned_all_in_loss, risk_per_trade_pct)
        if not all(math.isfinite(value) and value >= 0 for value in derived):
            return ExecutionRevalidationResult(allowed=False, reason="Derived execution risk is invalid; execution remains fail-closed.")

        total_outflow = q * effective_entry + entry_fee
        if not math.isfinite(total_outflow) or total_outflow > account.cash + 1e-9:
            return ExecutionRevalidationResult(allowed=False, reason="Authoritative sized quantity exceeds available Paper cash at next-open execution.")

        estimate = ExecutionRiskEstimate(
            effective_entry_price=effective_entry,
            estimated_stop_fill_price=estimated_stop_fill,
            quantity=q,
            price_loss=price_loss,
            entry_fee=entry_fee,
            estimated_exit_fee=estimated_exit_fee,
            planned_all_in_loss=planned_all_in_loss,
            risk_per_trade_pct=risk_per_trade_pct,
        )
        availability = self.context_builder.build(account, risk_per_trade_pct)
        if not availability.available or availability.context is None:
            return ExecutionRevalidationResult(allowed=False, estimate=estimate, context_availability=availability, reason="Complete authoritative RiskContext is unavailable at execution time.")

        risk = self.risk_service.evaluate(strategy, availability.context, policy or RiskPolicy())
        allowed = risk.decision == RiskDecision.ALLOW
        return ExecutionRevalidationResult(
            allowed=allowed,
            estimate=estimate,
            context_availability=availability,
            risk=risk,
            reason=(
                "Fresh Risk Guard ALLOW established at next-open execution."
                if allowed
                else f"Fresh Risk Guard decision is {risk.decision.value}; pending BUY must be cancelled."
            ),
        )
