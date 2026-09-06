from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.backtest.models import BacktestConfig
from backend.app.backtest.service import BacktestService
from backend.app.market.models import Candle
from backend.app.strategy.models import Assessment, StrategyEvidence, StrategyResult


def make_candle(index: int, base_price: float = 100.0, *, volume: float = 1000.0) -> Candle:
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=index)
    price = base_price + index * 2.0
    return Candle(
        timestamp=timestamp,
        symbol="BTCUSD",
        timeframe="1h",
        open=price,
        high=price + 1.5,
        low=price - 1.5,
        close=price + 0.5,
        volume=volume,
    )


def make_strategy(index: int, assessment: Assessment) -> StrategyResult:
    return StrategyResult(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=index),
        symbol="BTCUSD",
        timeframe="1h",
        score=5 if assessment in {Assessment.BULLISH, Assessment.STRONG_BULLISH} else -5 if assessment in {Assessment.BEARISH, Assessment.STRONG_BEARISH} else 0,
        normalized_score=100 if assessment in {Assessment.BULLISH, Assessment.STRONG_BULLISH} else 0,
        assessment=assessment,
        data_ready=True,
        evidence=[
            StrategyEvidence(
                indicator="EMA",
                condition="ema_fast > ema_slow",
                contribution=2,
                description="Test signal",
            )
        ],
    )


def test_config_validates_spec_boundaries() -> None:
    with pytest.raises(ValueError):
        BacktestConfig(initial_capital=0.0)
    with pytest.raises(ValueError):
        BacktestConfig(position_size_pct=0.0)
    with pytest.raises(ValueError):
        BacktestConfig(position_size_pct=101.0)
    with pytest.raises(ValueError):
        BacktestConfig(transaction_cost_pct=-0.01)
    with pytest.raises(ValueError):
        BacktestConfig(slippage_pct=-0.01)
    BacktestConfig(transaction_cost_pct=0.0)
    BacktestConfig(slippage_pct=0.0)


def test_no_lookahead_execution_uses_next_open() -> None:
    candles = [
        make_candle(0, base_price=100.0),
        make_candle(1, base_price=102.0),
        make_candle(2, base_price=108.0),
    ]
    strategies = [
        make_strategy(0, Assessment.BULLISH),
        make_strategy(1, Assessment.NEUTRAL),
        make_strategy(2, Assessment.NEUTRAL),
    ]

    result = BacktestService().evaluate(
        candles,
        strategies,
        BacktestConfig(position_size_pct=10.0, transaction_cost_pct=0.10, slippage_pct=0.05),
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_signal_timestamp == candles[0].timestamp
    assert trade.entry_timestamp == candles[1].timestamp
    assert trade.entry_price == pytest.approx(candles[1].open * 1.0005)
    assert trade.exit_signal_timestamp == candles[1].timestamp
    assert trade.exit_timestamp == candles[2].timestamp
    assert trade.exit_price == pytest.approx(candles[2].open * 0.9995)
    assert trade.exit_price != candles[1].close
    assert trade.entry_price != candles[0].close


def test_first_neutral_exit_signal_owns_next_open_execution() -> None:
    candles = [make_candle(index) for index in range(4)]
    strategies = [
        make_strategy(0, Assessment.BULLISH),
        make_strategy(1, Assessment.NEUTRAL),
        make_strategy(2, Assessment.NEUTRAL),
        make_strategy(3, Assessment.NEUTRAL),
    ]

    result = BacktestService().evaluate(candles, strategies)

    trade = result.trades[0]
    assert trade.exit_signal_timestamp == candles[1].timestamp
    assert trade.exit_timestamp == candles[2].timestamp
    assert trade.exit_price == pytest.approx(candles[2].open * 0.9995)


def test_first_bearish_exit_signal_owns_next_open_execution() -> None:
    candles = [make_candle(index) for index in range(4)]
    strategies = [
        make_strategy(0, Assessment.BULLISH),
        make_strategy(1, Assessment.BEARISH),
        make_strategy(2, Assessment.BEARISH),
        make_strategy(3, Assessment.BEARISH),
    ]

    result = BacktestService().evaluate(candles, strategies)

    trade = result.trades[0]
    assert trade.exit_signal_timestamp == candles[1].timestamp
    assert trade.exit_timestamp == candles[2].timestamp
    assert trade.exit_price == pytest.approx(candles[2].open * 0.9995)


def test_forced_exit_uses_last_close_and_slippage() -> None:
    candles = [
        make_candle(0, base_price=100.0),
        make_candle(1, base_price=103.0),
        make_candle(2, base_price=106.0),
    ]
    strategies = [
        make_strategy(0, Assessment.BULLISH),
        make_strategy(1, Assessment.BULLISH),
        make_strategy(2, Assessment.BULLISH),
    ]

    result = BacktestService().evaluate(
        candles,
        strategies,
        BacktestConfig(position_size_pct=10.0, transaction_cost_pct=0.10, slippage_pct=0.05),
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.forced_exit is True
    assert trade.exit_timestamp == candles[-1].timestamp
    assert trade.exit_price == pytest.approx(candles[-1].close * 0.9995)
    assert trade.exit_assessment == "FORCED_EXIT"


def test_position_size_and_costs_are_calculated_explicitly() -> None:
    candles = [
        make_candle(0, base_price=100.0),
        make_candle(1, base_price=101.0),
        make_candle(2, base_price=102.0),
    ]
    strategies = [
        make_strategy(0, Assessment.BULLISH),
        make_strategy(1, Assessment.NEUTRAL),
        make_strategy(2, Assessment.NEUTRAL),
    ]

    config = BacktestConfig(initial_capital=10000.0, position_size_pct=10.0, transaction_cost_pct=0.10, slippage_pct=0.05)
    result = BacktestService().evaluate(candles, strategies, config)
    trade = result.trades[0]

    target_allocation = 10000.0 * 0.10
    effective_entry_price = candles[1].open * (1 + 0.05 / 100.0)
    expected_quantity = target_allocation / (effective_entry_price * (1 + 0.10 / 100.0))
    expected_entry_notional = expected_quantity * effective_entry_price
    expected_entry_cost = expected_entry_notional * 0.10 / 100.0

    assert trade.quantity == pytest.approx(expected_quantity)
    assert trade.entry_transaction_cost == pytest.approx(expected_entry_cost)
    assert trade.entry_price == pytest.approx(effective_entry_price)
    assert (trade.entry_transaction_cost + trade.entry_price * trade.quantity) == pytest.approx(target_allocation, rel=1e-9)


def test_zero_trade_metrics_are_valid() -> None:
    candles = [make_candle(index) for index in range(5)]
    strategies = [make_strategy(index, Assessment.NEUTRAL) for index in range(5)]

    result = BacktestService().evaluate(candles, strategies)

    assert result.total_trades == 0
    assert result.win_rate_pct == 0.0
    assert result.profit_factor is None
    assert result.average_trade_pnl == 0.0
    assert result.gross_profit == 0.0
    assert result.gross_loss == 0.0
    assert result.final_equity == result.initial_capital
    assert not any(value != value for value in [result.gross_profit, result.gross_loss, result.average_trade_pnl])


def test_short_and_insufficient_data_never_open_positions() -> None:
    candles = [make_candle(0), make_candle(1), make_candle(2)]
    strategies = [
        make_strategy(0, Assessment.BEARISH),
        make_strategy(1, Assessment.STRONG_BEARISH),
        make_strategy(2, Assessment.NEUTRAL),
    ]

    result = BacktestService().evaluate(candles, strategies)
    assert result.total_trades == 0

    insufficient = [
        StrategyResult(
            timestamp=candles[0].timestamp,
            symbol="BTCUSD",
            timeframe="1h",
            score=0,
            normalized_score=0,
            assessment=Assessment.INSUFFICIENT_DATA,
            data_ready=False,
            evidence=[],
        ),
        make_strategy(1, Assessment.BULLISH),
        make_strategy(2, Assessment.NEUTRAL),
    ]
    assert BacktestService().evaluate(candles, insufficient).total_trades == 1

    no_exit = [
        make_strategy(0, Assessment.BULLISH),
        StrategyResult(
            timestamp=candles[1].timestamp,
            symbol="BTCUSD",
            timeframe="1h",
            score=0,
            normalized_score=0,
            assessment=Assessment.INSUFFICIENT_DATA,
            data_ready=False,
            evidence=[],
        ),
        make_strategy(2, Assessment.NEUTRAL),
        make_strategy(3, Assessment.NEUTRAL),
    ]
    no_exit_candles = [make_candle(index) for index in range(4)]
    result = BacktestService().evaluate(no_exit_candles, no_exit)
    assert result.trades[0].exit_signal_timestamp == no_exit_candles[2].timestamp
    assert result.trades[0].exit_timestamp == no_exit_candles[3].timestamp


def test_alignment_errors_are_rejected() -> None:
    candles = [make_candle(0), make_candle(1)]
    strategies = [make_strategy(0, Assessment.BULLISH), make_strategy(0, Assessment.BULLISH)]
    with pytest.raises(ValueError):
        BacktestService().evaluate(candles, strategies)

    with pytest.raises(ValueError):
        BacktestService().evaluate([make_candle(0), make_candle(0)], [make_strategy(0, Assessment.BULLISH), make_strategy(1, Assessment.BULLISH)])

    with pytest.raises(ValueError):
        BacktestService().evaluate([make_candle(0), make_candle(1)], [make_strategy(1, Assessment.BULLISH), make_strategy(2, Assessment.BULLISH)])


def test_determinism_and_immutability() -> None:
    candles = [make_candle(0), make_candle(1), make_candle(2)]
    strategies = [make_strategy(0, Assessment.BULLISH), make_strategy(1, Assessment.NEUTRAL), make_strategy(2, Assessment.NEUTRAL)]
    original_candles = [candle.model_copy() for candle in candles]
    original_strategies = [strategy.model_copy() for strategy in strategies]
    config = BacktestConfig()

    first = BacktestService().evaluate(candles, strategies, config)
    second = BacktestService().evaluate([candle.model_copy() for candle in candles], [strategy.model_copy() for strategy in strategies], config)

    assert first == second
    assert candles == original_candles
    assert strategies == original_strategies
    assert config == BacktestConfig()


def test_backtest_api_stays_calculation_only() -> None:
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    response = client.post(
        "/backtest/evaluate",
        json={
            "candles": [
                {"timestamp": "2024-01-01T00:00:00+00:00", "symbol": "BTCUSD", "timeframe": "1h", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000.0},
                {"timestamp": "2024-01-01T01:00:00+00:00", "symbol": "BTCUSD", "timeframe": "1h", "open": 101.0, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 1000.0},
            ],
            "strategy_results": [
                {"timestamp": "2024-01-01T00:00:00+00:00", "symbol": "BTCUSD", "timeframe": "1h", "score": 5, "normalized_score": 100, "assessment": "BULLISH", "data_ready": True, "evidence": []},
                {"timestamp": "2024-01-01T01:00:00+00:00", "symbol": "BTCUSD", "timeframe": "1h", "score": -5, "normalized_score": 0, "assessment": "BEARISH", "data_ready": True, "evidence": []},
            ],
            "config": {"initial_capital": 10000.0, "position_size_pct": 10.0, "transaction_cost_pct": 0.10, "slippage_pct": 0.05},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_trades"] == 1
    assert len(payload["trades"]) == 1
    trade = payload["trades"][0]
    assert trade["forced_exit"] is True
    assert trade["entry_timestamp"] == "2024-01-01T01:00:00Z"
    assert trade["entry_price"] == pytest.approx(101.0 * 1.0005)
    assert trade["exit_timestamp"] == "2024-01-01T01:00:00Z"
    assert trade["exit_price"] == pytest.approx(101.5 * 0.9995)
