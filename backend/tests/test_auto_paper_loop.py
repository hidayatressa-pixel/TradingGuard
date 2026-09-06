from datetime import datetime, timedelta, timezone

import pytest

from backend.app.market.models import Candle
from backend.app.paper.auto_loop import AutoPaperLoopService
from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskDecision
from backend.app.strategy.models import Assessment, StrategyResult

TS = datetime(2026, 9, 6, tzinfo=timezone.utc)


def candles(count: int, symbol: str = "BTCUSDT", timeframe: str = "1h") -> list[Candle]:
    result = []
    for i in range(count):
        base = 100.0 + i * 0.4
        result.append(Candle(timestamp=TS + timedelta(hours=i), symbol=symbol, timeframe=timeframe,
            open=base, high=base + 1.2, low=base - 1.0, close=base + 0.5, volume=1000.0 + i))
    return result


def bullish(candle: Candle) -> StrategyResult:
    return StrategyResult(timestamp=candle.timestamp, symbol=candle.symbol, timeframe=candle.timeframe,
        score=4, normalized_score=90, assessment=Assessment.BULLISH, data_ready=True, evidence=[])


def bearish(candle: Candle) -> StrategyResult:
    return StrategyResult(timestamp=candle.timestamp, symbol=candle.symbol, timeframe=candle.timeframe,
        score=-4, normalized_score=10, assessment=Assessment.STRONG_BEARISH, data_ready=True, evidence=[])


def started_loop() -> tuple[PaperTradingService, AutoPaperLoopService]:
    service = PaperTradingService(); service.start(PaperTradingConfig(transaction_cost_pct=0.0, slippage_pct=0.0))
    return service, AutoPaperLoopService(service)


def force_bullish(loop: AutoPaperLoopService, monkeypatch) -> None:
    monkeypatch.setattr(loop.indicators, "build_snapshots", lambda values: values)
    monkeypatch.setattr(loop.strategy, "build_results", lambda values: [bullish(values[-1])])


def test_first_auto_cycle_initializes_risk_day_and_can_schedule(monkeypatch) -> None:
    service, loop = started_loop(); force_bullish(loop, monkeypatch); data = candles(40)
    assert service.state().risk_day is None
    result = loop.cycle(data, risk_budget_pct=0.5, max_allocation_pct=20.0)
    assert service.state().risk_day == data[-2].timestamp.date().isoformat()
    assert result.strategy.timestamp == data[-2].timestamp
    assert result.entry is not None and result.entry.execution_permission_established is True and result.entry.scheduled is True
    assert result.authorization is result.entry
    assert result.authorization.gate is not None and result.authorization.gate.risk is not None
    assert result.authorization.gate.risk.decision == RiskDecision.ALLOW
    assert service.state().pending_entry is not None
    assert service.state().event_index == 1


def test_next_completed_candle_revalidates_and_executes_pending_sized_entry(monkeypatch) -> None:
    service, loop = started_loop(); force_bullish(loop, monkeypatch)
    first = loop.cycle(candles(40), risk_budget_pct=0.5, max_allocation_pct=20.0)
    assert first.entry is not None and first.entry.scheduled is True
    assert service.state().pending_entry is not None and service.state().open_position is None
    second = loop.cycle(candles(41), risk_budget_pct=0.5, max_allocation_pct=20.0)
    assert second.account.pending_entry is None
    assert second.account.open_position is not None and second.account.open_position.stop_loss_price is not None
    assert second.account.event_index == 2
    assert second.entry is None
    assert second.authorization is not None and second.authorization.gate is not None
    assert second.authorization.gate.risk is not None
    assert second.authorization.gate.risk.decision == RiskDecision.ALLOW
    assert second.mark_price == candles(41)[-1].close
    assert second.unrealized_pnl is not None
    assert second.unrealized_return_pct is not None


def test_same_completed_candle_is_idempotent_and_reports_pending_state(monkeypatch) -> None:
    service, loop = started_loop(); force_bullish(loop, monkeypatch); data = candles(40)
    first = loop.cycle(data); before = service.state().event_index
    repeated = loop.cycle(data)
    assert repeated.account.event_index == before
    assert repeated.account.open_position is None
    assert repeated.account.pending_entry is not None
    assert repeated.authorization == first.authorization
    assert "remains pending" in repeated.reason


def test_duplicate_active_position_reports_monitoring_not_setup_wait(monkeypatch) -> None:
    service, loop = started_loop(); force_bullish(loop, monkeypatch)
    loop.cycle(candles(40)); loop.cycle(candles(41))
    repeated = loop.cycle(candles(41))
    assert repeated.account.open_position is not None
    assert "remains active" in repeated.reason
    assert "setup" not in repeated.reason.lower()
    assert repeated.mark_price is not None and repeated.unrealized_pnl is not None


def test_strong_bearish_active_position_arms_exit_and_preserves_entry_authorization(monkeypatch) -> None:
    service, loop = started_loop(); force_bullish(loop, monkeypatch)
    loop.cycle(candles(40)); loop.cycle(candles(41))
    monkeypatch.setattr(loop.strategy, "build_results", lambda values: [bearish(values[-1])])
    result = loop.cycle(candles(42))
    assert result.strategy.assessment == Assessment.STRONG_BEARISH
    assert result.account.open_position is not None
    assert result.account.pending_exit is not None
    assert result.authorization is not None
    assert result.authorization.gate is not None and result.authorization.gate.risk is not None
    assert result.authorization.gate.risk.decision == RiskDecision.ALLOW
    assert "EXIT ARMED" in result.reason


def test_operational_instrument_is_locked_while_pending(monkeypatch) -> None:
    service, loop = started_loop(); force_bullish(loop, monkeypatch)
    loop.cycle(candles(40, "ETHUSDT", "1h"))
    assert service.state().pending_entry is not None
    with pytest.raises(ValueError, match="locked to ETHUSDT/1h"):
        loop.cycle(candles(41, "BTCUSDT", "1h"))
    assert service.state().pending_entry is not None
    assert service.state().pending_entry.symbol == "ETHUSDT"


def test_eligible_bullish_flat_cycle_never_returns_unevaluated_wait(monkeypatch) -> None:
    service, loop = started_loop(); force_bullish(loop, monkeypatch)
    result = loop.cycle(candles(40))
    assert result.entry is not None
    assert result.authorization is not None
    gate = result.authorization.gate
    assert gate is not None and gate.risk is not None
    assert gate.risk.decision in {RiskDecision.ALLOW, RiskDecision.WARNING, RiskDecision.BLOCK}
