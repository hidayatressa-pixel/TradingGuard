from datetime import datetime, timezone

import pytest

from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.integration import ProspectiveRiskGateService
from backend.app.risk.models import RiskDecision, RiskPolicy
from backend.app.risk_sizing.models import RiskSizingRequest
from backend.app.strategy.models import Assessment, StrategyResult


def strategy() -> StrategyResult:
    return StrategyResult(
        timestamp=datetime(2026, 9, 6, 7, 0, tzinfo=timezone.utc),
        symbol="BTCUSDT",
        timeframe="1h",
        score=4,
        normalized_score=90,
        assessment=Assessment.STRONG_BULLISH,
        data_ready=True,
        evidence=[],
    )


def account():
    paper = PaperTradingService().start(PaperTradingConfig())
    paper.risk_day = "2026-09-06"
    return paper


def sizing(risk_budget_pct: float = 0.5) -> RiskSizingRequest:
    return RiskSizingRequest(
        equity=10_000.0,
        entry_price=100.0,
        stop_loss_price=95.0,
        risk_budget_pct=risk_budget_pct,
        max_allocation_pct=20.0,
    )


def test_allow_when_all_authoritative_facts_are_within_limits() -> None:
    result = ProspectiveRiskGateService().evaluate(strategy(), account(), sizing(0.5))
    assert result.context_availability.available is True
    assert result.risk is not None
    assert result.risk.decision == RiskDecision.ALLOW
    assert result.execution_permission_established is True


def test_warning_does_not_establish_execution_permission() -> None:
    result = ProspectiveRiskGateService().evaluate(strategy(), account(), sizing(0.8))
    assert result.risk is not None
    assert result.risk.decision == RiskDecision.WARNING
    assert result.execution_permission_established is False


def test_block_does_not_establish_execution_permission() -> None:
    # No allocation cap here: the test must actually deliver >1% final risk
    # to Risk Guard. With the normal 20% allocation cap and a 5% stop,
    # final price-risk is capped at exactly 1%, which is WARNING by policy.
    request = RiskSizingRequest(
        equity=10_000.0,
        entry_price=100.0,
        stop_loss_price=95.0,
        risk_budget_pct=1.5,
        max_allocation_pct=None,
    )
    result = ProspectiveRiskGateService().evaluate(strategy(), account(), request)
    assert result.sizing.risk_per_trade_pct == pytest.approx(1.5)
    assert result.risk is not None
    assert result.risk.decision == RiskDecision.BLOCK
    assert result.execution_permission_established is False


def test_daily_loss_can_veto_otherwise_safe_trade_risk() -> None:
    paper = account()
    paper.day_start_equity = 10_000.0
    paper.realized_equity = 9_700.0
    result = ProspectiveRiskGateService().evaluate(strategy(), paper, sizing(0.5))
    assert result.risk is not None
    assert result.risk.decision == RiskDecision.BLOCK
    assert any(item.rule == "daily_loss" and item.status.value == "BLOCK" for item in result.risk.evidence)


def test_drawdown_can_veto_otherwise_safe_trade_risk() -> None:
    paper = account()
    paper.peak_realized_equity = 11_000.0
    paper.realized_equity = 9_900.0
    result = ProspectiveRiskGateService().evaluate(strategy(), paper, sizing(0.5))
    assert result.risk is not None
    assert result.risk.decision == RiskDecision.BLOCK
    assert any(item.rule == "drawdown" and item.status.value == "BLOCK" for item in result.risk.evidence)


def test_disabled_paper_account_is_blocked_by_kill_switch() -> None:
    paper = account()
    paper.active = False
    result = ProspectiveRiskGateService().evaluate(strategy(), paper, sizing(0.5))
    assert result.risk is not None
    assert result.risk.decision == RiskDecision.BLOCK
    assert result.execution_permission_established is False


def test_missing_risk_day_fails_closed_without_calling_risk_guard() -> None:
    paper = account()
    paper.risk_day = None
    result = ProspectiveRiskGateService().evaluate(strategy(), paper, sizing(0.5))
    assert result.context_availability.available is False
    assert result.risk is None
    assert result.execution_permission_established is False
    assert "risk_day" in result.context_availability.missing_facts


def test_allocation_cap_is_not_reinterpreted_as_trade_risk() -> None:
    request = RiskSizingRequest(
        equity=10_000.0,
        entry_price=100.0,
        stop_loss_price=95.0,
        risk_budget_pct=1.0,
        max_allocation_pct=10.0,
    )
    result = ProspectiveRiskGateService().evaluate(strategy(), account(), request)
    assert result.sizing.allocation_pct == pytest.approx(10.0)
    assert result.sizing.risk_per_trade_pct == pytest.approx(0.5)
    assert result.sizing.allocation_pct != result.sizing.risk_per_trade_pct
    assert result.risk is not None
    assert result.risk.decision == RiskDecision.ALLOW


def test_custom_policy_remains_authoritative() -> None:
    policy = RiskPolicy(max_risk_per_trade_pct=0.4, warning_risk_per_trade_pct=0.3)
    result = ProspectiveRiskGateService().evaluate(strategy(), account(), sizing(0.5), policy)
    assert result.risk is not None
    assert result.risk.decision == RiskDecision.BLOCK
