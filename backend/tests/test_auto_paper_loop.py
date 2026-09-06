from datetime import datetime, timedelta, timezone

from backend.app.market.models import Candle
from backend.app.paper.auto_loop import AutoPaperLoopService
from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.strategy.models import Assessment, StrategyResult

TS = datetime(2026, 9, 6, tzinfo=timezone.utc)


def candles(count: int) -> list[Candle]:
    result = []
    for i in range(count):
        base = 100.0 + i * 0.4
        result.append(Candle(
            timestamp=TS + timedelta(hours=i), symbol="BTCUSDT", timeframe="1h",
            open=base, high=base + 1.2, low=base - 1.0, close=base + 0.5,
            volume=1000.0 + i,
        ))
    return result


def bullish(candle: Candle) -> StrategyResult:
    return StrategyResult(
        timestamp=candle.timestamp, symbol=candle.symbol, timeframe=candle.timeframe,
        score=4, normalized_score=90, assessment=Assessment.BULLISH,
        data_ready=True, evidence=[],
    )


def started_loop() -> tuple[PaperTradingService, AutoPaperLoopService]:
    service = PaperTradingService()
    service.start(PaperTradingConfig(transaction_cost_pct=0.0, slippage_pct=0.0))
    return service, AutoPaperLoopService(service)


def force_bullish(loop: AutoPaperLoopService, monkeypatch) -> None:
    monkeypatch.setattr(loop.indicators, "build_snapshots", lambda values: values)
    monkeypatch.setattr(loop.strategy, "build_results", lambda values: [bullish(values[-1])])


def test_first_auto_cycle_initializes_risk_day_and_can_schedule(monkeypatch) -> None:
    service, loop = started_loop()
    force_bullish(loop, monkeypatch)
    assert service.state().risk_day is None

    result = loop.cycle(candles(40), risk_budget_pct=0.5, max_allocation_pct=20.0)

    assert service.state().risk_day == candles(40)[-1].timestamp.date().isoformat()
    assert result.entry is not None
    assert result.entry.execution_permission_established is True
    assert result.entry.scheduled is True
    assert service.state().pending_entry is not None
    assert service.state().event_index == 1


def test_next_new_candle_revalidates_and_executes_pending_sized_entry(monkeypatch) -> None:
    service, loop = started_loop()
    force_bullish(loop, monkeypatch)

    first = loop.cycle(candles(40), risk_budget_pct=0.5, max_allocation_pct=20.0)
    assert first.entry is not None and first.entry.scheduled is True
    assert service.state().pending_entry is not None
    assert service.state().open_position is None

    second = loop.cycle(candles(41), risk_budget_pct=0.5, max_allocation_pct=20.0)

    assert second.account.pending_entry is None
    assert second.account.open_position is not None
    assert second.account.open_position.stop_loss_price is not None
    assert second.account.event_index == 2


def test_same_candle_is_idempotent_and_does_not_advance_execution_clock(monkeypatch) -> None:
    service, loop = started_loop()
    force_bullish(loop, monkeypatch)
    loop.cycle(candles(40))
    before = service.state().event_index

    repeated = loop.cycle(candles(40))

    assert repeated.account.event_index == before
    assert repeated.account.open_position is None
    assert repeated.account.pending_entry is not None
    assert "already processed" in repeated.reason
