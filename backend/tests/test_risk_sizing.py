import math

import pytest
from pydantic import ValidationError

from backend.app.risk_sizing.models import RiskSizingRequest
from backend.app.risk_sizing.service import RiskSizingService


service = RiskSizingService()


def test_sizes_long_position_from_stop_risk() -> None:
    result = service.evaluate(RiskSizingRequest(
        equity=10_000.0,
        entry_price=100.0,
        stop_loss_price=95.0,
        risk_budget_pct=1.0,
    ))

    assert result.requested_risk_budget_amount == pytest.approx(100.0)
    assert result.stop_distance == pytest.approx(5.0)
    assert result.final_quantity == pytest.approx(20.0)
    assert result.final_notional == pytest.approx(2_000.0)
    assert result.risk_amount == pytest.approx(100.0)
    assert result.risk_per_trade_pct == pytest.approx(1.0)
    assert result.allocation_pct == pytest.approx(20.0)
    assert result.allocation_cap_applied is False
    assert result.costs_included_in_risk is False


def test_allocation_cap_reduces_actual_risk_without_aliasing_allocation_to_risk() -> None:
    result = service.evaluate(RiskSizingRequest(
        equity=10_000.0,
        entry_price=100.0,
        stop_loss_price=95.0,
        risk_budget_pct=1.0,
        max_allocation_pct=10.0,
    ))

    assert result.final_notional == pytest.approx(1_000.0)
    assert result.allocation_pct == pytest.approx(10.0)
    assert result.risk_amount == pytest.approx(50.0)
    assert result.risk_per_trade_pct == pytest.approx(0.5)
    assert result.risk_per_trade_pct != result.allocation_pct
    assert result.allocation_cap_applied is True


@pytest.mark.parametrize("stop", [100.0, 101.0])
def test_rejects_stop_not_below_long_entry(stop: float) -> None:
    with pytest.raises(ValidationError):
        RiskSizingRequest(
            equity=10_000.0,
            entry_price=100.0,
            stop_loss_price=stop,
            risk_budget_pct=1.0,
        )


@pytest.mark.parametrize("field", ["equity", "entry_price", "stop_loss_price", "risk_budget_pct"])
@pytest.mark.parametrize("value", [0.0, -1.0])
def test_rejects_non_positive_required_values(field: str, value: float) -> None:
    payload = {
        "equity": 10_000.0,
        "entry_price": 100.0,
        "stop_loss_price": 95.0,
        "risk_budget_pct": 1.0,
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        RiskSizingRequest(**payload)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field", ["equity", "entry_price", "stop_loss_price", "risk_budget_pct", "max_allocation_pct"])
def test_rejects_non_finite_values(field: str, value: float) -> None:
    payload = {
        "equity": 10_000.0,
        "entry_price": 100.0,
        "stop_loss_price": 95.0,
        "risk_budget_pct": 1.0,
        "max_allocation_pct": 20.0,
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        RiskSizingRequest(**payload)


@pytest.mark.parametrize("value", [0.0, -1.0, 100.1])
def test_rejects_invalid_allocation_cap(value: float) -> None:
    with pytest.raises(ValidationError):
        RiskSizingRequest(
            equity=10_000.0,
            entry_price=100.0,
            stop_loss_price=95.0,
            risk_budget_pct=1.0,
            max_allocation_pct=value,
        )


def test_cost_treatment_is_explicit() -> None:
    result = service.evaluate(RiskSizingRequest(
        equity=10_000.0,
        entry_price=100.0,
        stop_loss_price=99.0,
        risk_budget_pct=0.5,
    ))
    assert result.costs_included_in_risk is False
    assert "not included" in result.cost_treatment.lower()
