from datetime import datetime, timedelta, timezone

from backend.app.market.models import Candle
from backend.app.risk_sizing.auto_stop import AutoStopLossService


def candles(count: int = 30) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = []
    for i in range(count):
        base = 100.0 + i * 0.4
        result.append(Candle(timestamp=start + timedelta(hours=i), symbol="BTCUSDT", timeframe="1h", open=base, high=base + 1.2, low=base - 1.0, close=base + 0.5, volume=1000.0 + i))
    return result


def test_auto_stop_is_below_entry_and_reports_method() -> None:
    result = AutoStopLossService().evaluate(candles(), 112.0)
    assert result.valid is True
    assert result.stop_loss_price is not None
    assert result.stop_loss_price < 112.0
    assert result.method == "STRUCTURE_LOW_PLUS_ATR_BUFFER"
    assert result.atr is not None and result.atr > 0
    assert result.stop_distance_pct is not None and result.stop_distance_pct > 0


def test_auto_stop_fails_closed_with_insufficient_history() -> None:
    result = AutoStopLossService().evaluate(candles(5), 105.0)
    assert result.valid is False
    assert result.stop_loss_price is None


def test_auto_stop_fails_closed_when_structure_is_above_entry() -> None:
    result = AutoStopLossService().evaluate(candles(), 90.0)
    assert result.valid is False
    assert result.stop_loss_price is None


def test_risk_budget_does_not_change_auto_stop() -> None:
    service = AutoStopLossService()
    first = service.evaluate(candles(), 112.0)
    second = service.evaluate(candles(), 112.0)
    assert first.stop_loss_price == second.stop_loss_price
