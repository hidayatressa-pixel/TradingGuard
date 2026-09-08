import math

import pytest

from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.context import PaperRiskContextBuilder


def account():
    return PaperTradingService().start(PaperTradingConfig())


def initialized_account():
    paper = account()
    paper.risk_day = "2026-09-06"
    return paper


def test_context_available_after_authoritative_baselines_exist() -> None:
    paper = initialized_account()
    result = PaperRiskContextBuilder().build(paper, risk_per_trade_pct=1.0)
    assert result.available is True
    assert result.context is not None
    assert result.context.risk_per_trade_pct == pytest.approx(1.0)
    assert result.context.daily_loss_pct == pytest.approx(0.0)
    assert result.context.current_drawdown_pct == pytest.approx(0.0)
    assert result.context.total_exposure_pct == pytest.approx(0.0)
    assert result.context.open_positions == 0


def test_context_requires_initialized_risk_day() -> None:
    result = PaperRiskContextBuilder().build(account(), risk_per_trade_pct=1.0)
    assert result.available is False
    assert result.context is None
    assert "risk_day" in result.missing_facts


def test_daily_loss_and_drawdown_are_derived_from_distinct_baselines() -> None:
    paper = initialized_account()
    paper.day_start_equity = 9_800.0
    paper.peak_realized_equity = 10_500.0
    paper.realized_equity = 9_500.0
    result = PaperRiskContextBuilder().build(paper, risk_per_trade_pct=0.5)
    assert result.available is True
    assert result.context is not None
    assert result.context.daily_loss_pct == pytest.approx((300.0 / 9_800.0) * 100.0)
    assert result.context.current_drawdown_pct == pytest.approx((1_000.0 / 10_500.0) * 100.0)


def test_gains_do_not_become_negative_loss_or_drawdown() -> None:
    paper = initialized_account()
    paper.day_start_equity = 10_000.0
    paper.peak_realized_equity = 10_500.0
    paper.realized_equity = 10_500.0
    result = PaperRiskContextBuilder().build(paper, risk_per_trade_pct=0.5)
    assert result.context is not None
    assert result.context.daily_loss_pct == 0.0
    assert result.context.current_drawdown_pct == 0.0


def test_missing_sizing_risk_is_reported_not_converted_to_zero() -> None:
    result = PaperRiskContextBuilder().build(initialized_account(), risk_per_trade_pct=None)
    assert result.available is False
    assert "risk_per_trade_pct" in result.missing_facts


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -1.0])
def test_invalid_sizing_risk_remains_unavailable(value: float) -> None:
    result = PaperRiskContextBuilder().build(initialized_account(), risk_per_trade_pct=value)
    assert result.available is False
    assert "risk_per_trade_pct" in result.missing_facts


def test_paper_allocation_is_never_used_as_risk_per_trade() -> None:
    paper = initialized_account()
    result = PaperRiskContextBuilder().build(paper, risk_per_trade_pct=None)
    assert paper.config.position_size_pct == 10.0
    assert result.available is False
    assert "risk_per_trade_pct" in result.missing_facts
