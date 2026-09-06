from __future__ import annotations

import math

from backend.app.risk_sizing.models import RiskSizingRequest, RiskSizingResult


class RiskSizingService:
    """Calculate prospective long-position price risk without granting execution permission."""

    def evaluate(self, request: RiskSizingRequest) -> RiskSizingResult:
        stop_distance = request.entry_price - request.stop_loss_price
        stop_distance_pct = (stop_distance / request.entry_price) * 100.0
        requested_risk_amount = request.equity * (request.risk_budget_pct / 100.0)
        quantity_by_risk = requested_risk_amount / stop_distance
        notional_by_risk = quantity_by_risk * request.entry_price

        final_notional = notional_by_risk
        allocation_cap_applied = False
        if request.max_allocation_pct is not None:
            max_allocation_amount = request.equity * (request.max_allocation_pct / 100.0)
            if final_notional > max_allocation_amount:
                final_notional = max_allocation_amount
                allocation_cap_applied = True

        final_quantity = final_notional / request.entry_price
        risk_amount = final_quantity * stop_distance
        risk_per_trade_pct = (risk_amount / request.equity) * 100.0
        allocation_pct = (final_notional / request.equity) * 100.0

        values = (
            stop_distance,
            stop_distance_pct,
            requested_risk_amount,
            quantity_by_risk,
            notional_by_risk,
            final_notional,
            final_quantity,
            risk_amount,
            risk_per_trade_pct,
            allocation_pct,
        )
        if not all(math.isfinite(value) and value >= 0 for value in values):
            raise ValueError("risk sizing produced an invalid or non-finite result.")

        return RiskSizingResult(
            equity=request.equity,
            entry_price=request.entry_price,
            stop_loss_price=request.stop_loss_price,
            stop_distance=stop_distance,
            stop_distance_pct=stop_distance_pct,
            requested_risk_budget_pct=request.risk_budget_pct,
            requested_risk_budget_amount=requested_risk_amount,
            max_allocation_pct=request.max_allocation_pct,
            quantity_by_risk=quantity_by_risk,
            notional_by_risk=notional_by_risk,
            final_quantity=final_quantity,
            final_notional=final_notional,
            risk_amount=risk_amount,
            risk_per_trade_pct=risk_per_trade_pct,
            allocation_pct=allocation_pct,
            allocation_cap_applied=allocation_cap_applied,
        )
