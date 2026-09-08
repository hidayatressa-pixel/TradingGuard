from datetime import datetime, timezone

import pytest

from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.orchestration import AutoPaperEntryOrchestrator
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskPolicy
from backend.app.strategy.models import Assessment, StrategyResult

TS = datetime(2026, 9, 6, tzinfo=timezone.utc)


def strategy(assessment: Assessment = Assessment.BULLISH, ready: bool = True) -> StrategyResult:
    return StrategyResult(
        timestamp=TS,
        symbol="BTCUSDT",
        timeframe="1h",
        score=4,
        normalized_score=90,
        assessment=assessment,
        data_ready=ready,
        evidence=[],
    )


def started(*, position_size_pct: float = 10.0) -> PaperTradingService:
    service = PaperTradingService()
    service.start(PaperTradingConfig(position_size_pct=position_size_pct, transaction_cost_pct=0.0, slippage_pct=0.0))
    service.state().risk_day = TS.date().isoformat()
    return service


def test_allow_schedules_exact_authoritative_sizing_quantity() -> None:
    service = started(position_size_pct=1.0)
    result = AutoPaperEntryOrchestrator(service).evaluate_and_schedule(
        strategy=strategy(),
        reference_entry_price=100.0,
        stop_loss_price=95.0,
        risk_budget_pct=0.5,
    )
    assert result.scheduled is True
    assert result.gate is not None
    assert service.state().pending_entry is not None
    assert service.state().pending_entry.quantity == pytest.approx(result.gate.sizing.final_quantity)
    assert service.state().pending_entry.quantity == pytest.approx(10.0)
    assert service.state().pending_entry.stop_loss_price == pytest.approx(95.0)


def test_position_size_pct_is_not_used_as_risk_budget() -> None:
    service = started(position_size_pct=1.0)
    result = AutoPaperEntryOrchestrator(service).evaluate_and_schedule(
        strategy=strategy(), reference_entry_price=100.0, stop_loss_price=95.0, risk_budget_pct=0.5
    )
    assert result.gate is not None
    assert result.gate.sizing.requested_risk_budget_pct == pytest.approx(0.5)
    assert result.gate.sizing.risk_per_trade_pct == pytest.approx(0.5)
    assert service.state().pending_entry.quantity == pytest.approx(10.0)


def test_authoritative_paper_equity_is_used_for_sizing() -> None:
    service = started()
    service.state().realized_equity = 8000.0
    service.state().cash = 8000.0
    service.state().day_start_equity = 8000.0
    service.state().peak_realized_equity = 8000.0
    result = AutoPaperEntryOrchestrator(service).evaluate_and_schedule(
        strategy=strategy(), reference_entry_price=100.0, stop_loss_price=95.0, risk_budget_pct=1.0
    )
    assert result.gate is not None
    assert result.gate.sizing.equity == pytest.approx(8000.0)
    assert result.gate.sizing.final_quantity == pytest.approx(16.0)


def test_warning_does_not_schedule() -> None:
    service = started()
    result = AutoPaperEntryOrchestrator(service).evaluate_and_schedule(
        strategy=strategy(),
        reference_entry_price=100.0,
        stop_loss_price=95.0,
        risk_budget_pct=0.8,
        policy=RiskPolicy(max_risk_per_trade_pct=1.0, warning_risk_per_trade_pct=0.75),
    )
    assert result.scheduled is False
    assert result.gate is not None and result.gate.risk is not None
    assert result.gate.risk.decision.value == "WARNING"
    assert service.state().pending_entry is None


def test_block_does_not_schedule() -> None:
    service = started()
    result = AutoPaperEntryOrchestrator(service).evaluate_and_schedule(
        strategy=strategy(),
        reference_entry_price=100.0,
        stop_loss_price=95.0,
        risk_budget_pct=1.5,
        policy=RiskPolicy(max_risk_per_trade_pct=1.0, warning_risk_per_trade_pct=0.75),
    )
    assert result.scheduled is False
    assert result.gate is not None and result.gate.risk is not None
    assert result.gate.risk.decision.value == "BLOCK"
    assert service.state().pending_entry is None


def test_ineligible_strategy_does_not_run_entry_pipeline() -> None:
    service = started()
    result = AutoPaperEntryOrchestrator(service).evaluate_and_schedule(
        strategy=strategy(Assessment.NEUTRAL), reference_entry_price=100.0, stop_loss_price=95.0, risk_budget_pct=1.0
    )
    assert result.scheduled is False
    assert result.gate is None
    assert service.state().pending_entry is None


def test_inactive_paper_fails_closed() -> None:
    service = PaperTradingService()
    service.start(PaperTradingConfig())
    service.reset()
    result = AutoPaperEntryOrchestrator(service).evaluate_and_schedule(
        strategy=strategy(), reference_entry_price=100.0, stop_loss_price=95.0, risk_budget_pct=1.0
    )
    assert result.scheduled is False
    assert service.state().pending_entry is None


def test_allocation_cap_reduces_quantity_without_becoming_risk_budget() -> None:
    service = started()
    result = AutoPaperEntryOrchestrator(service).evaluate_and_schedule(
        strategy=strategy(), reference_entry_price=100.0, stop_loss_price=95.0, risk_budget_pct=1.0, max_allocation_pct=10.0
    )
    assert result.scheduled is True
    assert result.gate is not None
    assert result.gate.sizing.allocation_cap_applied is True
    assert result.gate.sizing.final_quantity == pytest.approx(10.0)
    assert result.gate.sizing.risk_per_trade_pct == pytest.approx(0.5)
