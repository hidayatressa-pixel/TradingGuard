import math

import pytest

from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.context import PaperRiskContextBuilder


def account():
    return PaperTradingService().start(PaperTradingConfig())


def test_complete_context_is_unavailable_without_authoritative_baselines() -> None:
    result = PaperRiskContextBuilder().build(account(), risk_per_trade_pct=1.0)

    assert result.available is False
    assert result.context is None
    assert "daily_loss_pct" in result.missing_facts
    assert "current_drawdown_pct" in result.missing_facts
    assert "risk_per_trade_pct" not in result.missing_facts
    assert "fail-closed" in result.reason


def test_missing_sizing_risk_is_reported_not_converted_to_zero() -> None:
    result = PaperRiskContextBuilder().build(account(), risk_per_trade_pct=None)

    assert result.available is False
    assert result.context is None
    assert "risk_per_trade_pct" in result.missing_facts


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -1.0])
def test_invalid_sizing_risk_remains_unavailable(value: float) -> None:
    result = PaperRiskContextBuilder().build(account(), risk_per_trade_pct=value)

    assert result.available is False
    assert result.context is None
    assert "risk_per_trade_pct" in result.missing_facts


def test_paper_allocation_is_never_used_as_risk_per_trade() -> None:
    paper = account()
    result = PaperRiskContextBuilder().build(paper, risk_per_trade_pct=None)

    assert paper.config.position_size_pct == 10.0
    assert result.available is False
    assert "risk_per_trade_pct" in result.missing_facts
