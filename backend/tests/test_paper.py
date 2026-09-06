from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app, paper_service
from backend.app.market.models import Candle
from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskDecision, RiskResult
from backend.app.strategy.models import Assessment, StrategyResult


BASE_TIME = datetime(2024, 1, 1, tzinfo=timezone.utc)


def candle(index: int, *, symbol: str = "BTCUSD", timeframe: str = "1h") -> Candle:
    price = 100.0 + index * 2.0
    return Candle(
        timestamp=BASE_TIME + timedelta(hours=index),
        symbol=symbol,
        timeframe=timeframe,
        open=price,
        high=price + 1.0,
        low=price - 1.0,
        close=price + 0.5,
        volume=1000.0,
    )


def priced_candle(index: int, price: float) -> Candle:
    return Candle(
        timestamp=BASE_TIME + timedelta(hours=index),
        symbol="BTCUSD",
        timeframe="1h",
        open=price,
        high=price + 1.0,
        low=price - 1.0,
        close=price + 0.5,
        volume=1000.0,
    )


def strategy(index: int, assessment: Assessment, *, data_ready: bool = True) -> StrategyResult:
    return StrategyResult(
        timestamp=BASE_TIME + timedelta(hours=index),
        symbol="BTCUSD",
        timeframe="1h",
        score=5 if assessment in {Assessment.BULLISH, Assessment.STRONG_BULLISH} else -5 if assessment in {Assessment.BEARISH, Assessment.STRONG_BEARISH} else 0,
        normalized_score=100 if assessment in {Assessment.BULLISH, Assessment.STRONG_BULLISH} else 0,
        assessment=assessment,
        data_ready=data_ready,
        evidence=[],
    )


def risk(index: int, decision: RiskDecision = RiskDecision.ALLOW) -> RiskResult:
    return RiskResult(
        timestamp=BASE_TIME + timedelta(hours=index),
        symbol="BTCUSD",
        timeframe="1h",
        strategy_assessment="BULLISH",
        strategy_score=5,
        decision=decision,
        data_ready=True,
        evidence=[],
        block_reasons=[],
        warning_reasons=[],
    )


def started_service() -> PaperTradingService:
    service = PaperTradingService()
    service.start()
    return service


def test_config_defaults_and_finite_validation() -> None:
    config = PaperTradingConfig()
    assert config.initial_capital == 10000.0
    assert config.position_size_pct == 10.0
    assert config.transaction_cost_pct == 0.10
    assert config.slippage_pct == 0.05
    for field in ("initial_capital", "position_size_pct", "transaction_cost_pct", "slippage_pct"):
        with pytest.raises(ValidationError):
            PaperTradingConfig(**{field: float("nan")})
        with pytest.raises(ValidationError):
            PaperTradingConfig(**{field: float("inf")})


def test_config_boundaries_and_start_state() -> None:
    for kwargs in (
        {"initial_capital": 0.0},
        {"position_size_pct": 0.0},
        {"position_size_pct": -1.0},
        {"position_size_pct": 101.0},
        {"transaction_cost_pct": -0.1},
        {"slippage_pct": -0.1},
    ):
        with pytest.raises(ValidationError):
            PaperTradingConfig(**kwargs)

    service = started_service()
    account = service.state()
    assert account.cash == 10000.0
    assert account.realized_equity == 10000.0
    assert account.open_position is None
    assert account.closed_trades == []
    assert account.total_transaction_cost == 0.0


def test_risk_allow_required_and_warning_block_do_not_enter() -> None:
    for decision in (RiskDecision.WARNING, RiskDecision.BLOCK):
        service = started_service()
        service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0, decision))
        assert service.state().pending_entry is None

    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    assert service.state().pending_entry is not None


def test_long_only_and_insufficient_data_do_not_enter_or_exit() -> None:
    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.BEARISH), risk(0))
    assert service.state().open_position is None
    service.process_candle(candle(1), strategy(1, Assessment.INSUFFICIENT_DATA, data_ready=False), risk(1))
    assert service.state().open_position is None

    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(candle(1), strategy(1, Assessment.INSUFFICIENT_DATA, data_ready=False), risk(1))
    assert service.state().open_position is not None
    assert service.state().pending_exit is None


def test_next_bar_entry_and_accounting() -> None:
    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    pending = service.state().pending_entry
    assert pending is not None
    assert service.state().open_position is None

    service.process_candle(candle(1), strategy(1, Assessment.BULLISH), risk(1))
    position = service.state().open_position
    assert position is not None
    assert position.entry_timestamp == candle(1).timestamp
    assert position.entry_price == pytest.approx(candle(1).open * 1.0005)
    assert position.entry_signal_timestamp == candle(0).timestamp
    assert position.entry_notional + position.entry_transaction_cost <= 1000.0 + 1e-9
    assert service.state().cash >= 0


def test_first_pending_exit_is_not_rescheduled_for_neutral_or_bearish() -> None:
    for exit_assessment in (Assessment.NEUTRAL, Assessment.BEARISH):
        service = started_service()
        service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
        service.process_candle(candle(1), strategy(1, exit_assessment), risk(1))
        pending = service.state().pending_exit
        assert pending is not None
        assert pending.signal_timestamp == candle(1).timestamp
        service.process_candle(candle(2), strategy(2, exit_assessment), risk(2))
        assert service.state().open_position is None
        assert len(service.state().closed_trades) == 1
        trade = service.state().closed_trades[0]
        assert trade.exit_signal_timestamp == candle(1).timestamp
        assert trade.exit_timestamp == candle(2).timestamp
        assert trade.exit_price == pytest.approx(candle(2).open * 0.9995)


def test_exit_accounting_and_realized_metrics_exclude_unrealized_pnl() -> None:
    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(candle(1), strategy(1, Assessment.BULLISH), risk(1))
    open_equity = service.performance().realized_equity
    service.process_candle(candle(2), strategy(2, Assessment.NEUTRAL), risk(2))
    service.process_candle(candle(3), strategy(3, Assessment.NEUTRAL), risk(3))
    performance = service.performance()
    trade = service.state().closed_trades[0]
    assert performance.total_closed_trades == 1
    assert performance.realized_equity == service.state().cash
    assert performance.realized_net_profit == pytest.approx(trade.net_pnl)
    assert performance.realized_equity != open_equity
    assert service.state().open_position is None
    assert performance.total_transaction_cost == pytest.approx(trade.transaction_cost)


def test_event_validation_kill_switch_and_reset() -> None:
    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.account.config.paper_trading_enabled = False
    service.process_candle(candle(1), strategy(1, Assessment.BULLISH), risk(1))
    assert service.state().pending_entry is None

    with pytest.raises(ValueError):
        service.process_candle(candle(1), strategy(1, Assessment.BULLISH), risk(1))
    with pytest.raises(ValueError):
        service.process_candle(candle(0, symbol="ETHUSD"), strategy(0, Assessment.BULLISH), risk(0))

    reset = service.reset()
    assert reset.active is False
    assert reset.event_index == 0
    service.start(PaperTradingConfig())
    service.process_candle(candle(0), strategy(0, Assessment.NEUTRAL), risk(0))


def test_api_paper_start_process_state_reset() -> None:
    client = TestClient(app)
    client.post("/paper/reset")
    start = client.post("/paper/start", json={"config": {"initial_capital": 10000.0}})
    assert start.status_code == 200
    duplicate = client.post("/paper/start", json={})
    assert duplicate.status_code == 400

    payload = {
        "candle": {
            "timestamp": "2024-01-01T00:00:00+00:00",
            "symbol": "BTCUSD",
            "timeframe": "1h",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000.0,
        },
        "strategy": {
            "timestamp": "2024-01-01T00:00:00+00:00",
            "symbol": "BTCUSD",
            "timeframe": "1h",
            "score": 5,
            "normalized_score": 100,
            "assessment": "BULLISH",
            "data_ready": True,
            "evidence": [],
        },
        "risk": {
            "timestamp": "2024-01-01T00:00:00+00:00",
            "symbol": "BTCUSD",
            "timeframe": "1h",
            "strategy_assessment": "BULLISH",
            "strategy_score": 5,
            "decision": "ALLOW",
            "data_ready": True,
            "evidence": [],
            "block_reasons": [],
            "warning_reasons": [],
        },
    }
    process = client.post("/paper/process", json=payload)
    assert process.status_code == 200
    assert process.json()["pending_entry"]["action"] == "ENTRY"
    assert client.get("/paper/state").status_code == 200
    assert client.get("/paper/performance").status_code == 200
    reset = client.post("/paper/reset")
    assert reset.status_code == 200
    assert reset.json()["active"] is False


def test_processing_before_start_is_rejected() -> None:
    service = PaperTradingService()
    with pytest.raises(ValueError):
        service.process_candle(candle(0), strategy(0, Assessment.NEUTRAL), risk(0))


def test_strong_bullish_and_neutral_entry_rules() -> None:
    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.STRONG_BULLISH), risk(0))
    assert service.state().pending_entry is not None

    neutral_service = started_service()
    neutral_service.process_candle(candle(0), strategy(0, Assessment.NEUTRAL), risk(0))
    assert neutral_service.state().pending_entry is None


def test_disabled_paper_mode_prevents_and_cancels_entry() -> None:
    service = PaperTradingService()
    service.start(PaperTradingConfig(paper_trading_enabled=False))
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    assert service.state().pending_entry is None

    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.state().config.paper_trading_enabled = False
    service.process_candle(candle(1), strategy(1, Assessment.BULLISH), risk(1))
    assert service.state().pending_entry is None
    assert service.state().open_position is None


def test_full_position_size_with_fee_never_overspends_cash() -> None:
    service = PaperTradingService()
    service.start(PaperTradingConfig(position_size_pct=100.0, transaction_cost_pct=0.10))
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(candle(1), strategy(1, Assessment.BULLISH), risk(1))
    account = service.state()
    assert account.cash >= 0
    assert account.open_position is not None
    assert account.open_position.entry_notional + account.open_position.entry_transaction_cost <= 10000.0 + 1e-9


def test_no_pyramiding_after_long_position_exists() -> None:
    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(candle(1), strategy(1, Assessment.BULLISH), risk(1))
    first_position = service.state().open_position
    service.process_candle(candle(2), strategy(2, Assessment.STRONG_BULLISH), risk(2))
    assert service.state().open_position == first_position
    assert service.state().pending_entry is None


def test_strong_bearish_schedules_exit() -> None:
    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(candle(1), strategy(1, Assessment.BULLISH), risk(1))
    service.process_candle(candle(2), strategy(2, Assessment.STRONG_BEARISH), risk(2))
    assert service.state().pending_exit is not None
    assert service.state().pending_exit.assessment == Assessment.STRONG_BEARISH.value


def test_exact_trade_pricing_fees_pnl_and_return() -> None:
    config = PaperTradingConfig(
        initial_capital=1000.0,
        position_size_pct=50.0,
        transaction_cost_pct=1.0,
        slippage_pct=2.0,
    )
    service = PaperTradingService()
    service.start(config)
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(candle(1), strategy(1, Assessment.NEUTRAL), risk(1))
    service.process_candle(candle(2), strategy(2, Assessment.NEUTRAL), risk(2))
    trade = service.state().closed_trades[0]

    entry_price = candle(1).open * 1.02
    allocation = 1000.0 * 0.50
    quantity = allocation / (entry_price * 1.01)
    entry_notional = quantity * entry_price
    entry_fee = entry_notional * 0.01
    exit_price = candle(2).open * 0.98
    exit_notional = quantity * exit_price
    exit_fee = exit_notional * 0.01
    gross_pnl = (exit_price - entry_price) * quantity
    net_pnl = gross_pnl - entry_fee - exit_fee
    committed = entry_notional + entry_fee

    assert trade.entry_price == pytest.approx(entry_price)
    assert trade.exit_price == pytest.approx(exit_price)
    assert trade.entry_transaction_cost == pytest.approx(entry_fee)
    assert trade.exit_transaction_cost == pytest.approx(exit_fee)
    assert trade.gross_pnl == pytest.approx(gross_pnl)
    assert trade.net_pnl == pytest.approx(net_pnl)
    assert trade.return_pct == pytest.approx((net_pnl / committed) * 100.0)


def test_completed_trade_cash_equity_and_metrics() -> None:
    service = PaperTradingService()
    service.start(PaperTradingConfig(transaction_cost_pct=0.0, slippage_pct=0.0))
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(candle(1), strategy(1, Assessment.NEUTRAL), risk(1))
    service.process_candle(candle(2), strategy(2, Assessment.NEUTRAL), risk(2))
    account = service.state()
    trade = account.closed_trades[0]
    performance = service.performance()
    assert account.cash == pytest.approx(account.realized_equity)
    assert account.realized_equity == pytest.approx(account.initial_capital + sum(item.net_pnl for item in account.closed_trades))
    assert performance.winning_trades == 1
    assert performance.losing_trades == 0
    assert performance.breakeven_trades == 0
    assert performance.gross_profit == pytest.approx(trade.net_pnl)
    assert performance.gross_loss == 0.0
    assert performance.profit_factor is None
    assert performance.average_trade_pnl == pytest.approx(trade.net_pnl)
    assert performance.expected_value == pytest.approx(performance.average_trade_pnl)
    assert performance.realized_return_pct == pytest.approx((trade.net_pnl / account.initial_capital) * 100.0)
    assert performance.total_transaction_cost == pytest.approx(0.0)


def test_losing_trade_and_profit_factor() -> None:
    service = PaperTradingService()
    service.start(PaperTradingConfig(transaction_cost_pct=0.0, slippage_pct=0.0))
    service.process_candle(priced_candle(0, 100.0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(priced_candle(1, 102.0), strategy(1, Assessment.BEARISH), risk(1))
    service.process_candle(priced_candle(2, 90.0), strategy(2, Assessment.BEARISH), risk(2))
    performance = service.performance()
    assert performance.winning_trades == 0
    assert performance.losing_trades == 1
    assert performance.breakeven_trades == 0
    assert performance.gross_profit == 0.0
    assert performance.gross_loss == pytest.approx(abs(service.state().closed_trades[0].net_pnl))
    assert performance.profit_factor == 0.0


def test_breakeven_trade_metrics() -> None:
    service = PaperTradingService()
    service.start(PaperTradingConfig(transaction_cost_pct=0.0, slippage_pct=0.0))
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(candle(1), strategy(1, Assessment.NEUTRAL), risk(1))
    service.process_candle(candle(2), strategy(2, Assessment.NEUTRAL), risk(2))
    service.state().closed_trades[0].net_pnl = 0.0
    performance = service.performance()
    assert performance.breakeven_trades == 1
    assert performance.winning_trades == 0
    assert performance.losing_trades == 0


def test_two_trade_accounting_invariant_uses_updated_equity() -> None:
    service = PaperTradingService()
    service.start(PaperTradingConfig(transaction_cost_pct=0.0, slippage_pct=0.0, position_size_pct=50.0))
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(candle(1), strategy(1, Assessment.NEUTRAL), risk(1))
    service.process_candle(candle(2), strategy(2, Assessment.NEUTRAL), risk(2))
    account = service.state()
    assert account.cash == pytest.approx(account.realized_equity)
    assert account.realized_equity == pytest.approx(account.initial_capital + sum(item.net_pnl for item in account.closed_trades))
    first_equity = account.realized_equity
    service.process_candle(candle(3), strategy(3, Assessment.BULLISH), risk(3))
    service.process_candle(candle(4), strategy(4, Assessment.BULLISH), risk(4))
    second_position = service.state().open_position
    assert second_position is not None
    assert second_position.entry_notional == pytest.approx(first_equity * 0.50)
    service.process_candle(candle(5), strategy(5, Assessment.NEUTRAL), risk(5))
    service.process_candle(candle(6), strategy(6, Assessment.NEUTRAL), risk(6))
    account = service.state()
    assert account.cash == pytest.approx(account.realized_equity)
    assert account.realized_equity == pytest.approx(account.initial_capital + sum(item.net_pnl for item in account.closed_trades))


def test_pending_action_ordering_allows_new_entry_only_after_exit_fill() -> None:
    service = started_service()
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    assert service.state().pending_entry is not None
    service.process_candle(candle(1), strategy(1, Assessment.NEUTRAL), risk(1))
    assert service.state().open_position is not None
    assert service.state().pending_exit is not None
    service.process_candle(candle(2), strategy(2, Assessment.BULLISH), risk(2))
    assert service.state().open_position is None
    assert service.state().closed_trades[0].exit_timestamp == candle(2).timestamp
    assert service.state().pending_entry is not None
    assert service.state().pending_entry.execute_index == 3


def test_event_validation_and_input_immutability() -> None:
    service = started_service()
    current_candle = candle(0)
    current_strategy = strategy(0, Assessment.BULLISH)
    current_risk = risk(0)
    candle_copy = current_candle.model_copy(deep=True)
    strategy_copy = current_strategy.model_copy(deep=True)
    risk_copy = current_risk.model_copy(deep=True)
    service.process_candle(current_candle, current_strategy, current_risk)
    assert current_candle == candle_copy
    assert current_strategy == strategy_copy
    assert current_risk == risk_copy

    with pytest.raises(ValueError):
        service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    with pytest.raises(ValueError):
        service.process_candle(candle(0, symbol="ETHUSD"), strategy(1, Assessment.BULLISH), risk(1))
    with pytest.raises(ValueError):
        service.process_candle(candle(1, timeframe="4h"), strategy(1, Assessment.BULLISH), risk(1))
    with pytest.raises(ValueError):
        service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))


def test_reset_clears_state_and_preserves_config_for_next_start() -> None:
    config = PaperTradingConfig(initial_capital=4321.0, position_size_pct=25.0)
    service = PaperTradingService()
    service.start(config)
    service.process_candle(candle(0), strategy(0, Assessment.BULLISH), risk(0))
    service.process_candle(candle(1), strategy(1, Assessment.NEUTRAL), risk(1))
    reset = service.reset()
    assert reset.open_position is None
    assert reset.pending_entry is None
    assert reset.pending_exit is None
    assert reset.closed_trades == []
    assert reset.total_transaction_cost == 0.0
    assert reset.last_event_timestamp is None
    assert reset.event_index == 0
    assert reset.config == config
    restarted = service.start()
    assert restarted.initial_capital == 4321.0
    assert restarted.config.position_size_pct == 25.0


def test_malformed_paper_api_requests_and_sequential_entry() -> None:
    client = TestClient(app)
    client.post("/paper/reset")
    assert client.post("/paper/process", json={}).status_code == 400
    assert client.post("/paper/start", json={"config": {"initial_capital": -1.0}}).status_code == 400
    assert client.post("/paper/start", json={}).status_code == 200
    assert client.post("/paper/process", json={"candle": {}}).status_code == 400

    base = {
        "candle": {
            "timestamp": "2024-01-01T00:00:00+00:00", "symbol": "BTCUSD", "timeframe": "1h",
            "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000.0,
        },
        "strategy": {
            "timestamp": "2024-01-01T00:00:00+00:00", "symbol": "BTCUSD", "timeframe": "1h",
            "score": 5, "normalized_score": 100, "assessment": "BULLISH", "data_ready": True, "evidence": [],
        },
        "risk": {
            "timestamp": "2024-01-01T00:00:00+00:00", "symbol": "BTCUSD", "timeframe": "1h",
            "strategy_assessment": "BULLISH", "strategy_score": 5, "decision": "ALLOW", "data_ready": True,
            "evidence": [], "block_reasons": [], "warning_reasons": [],
        },
    }
    first = client.post("/paper/process", json=base)
    assert first.status_code == 200
    assert first.json()["pending_entry"]["action"] == "ENTRY"
    second = deepcopy(base)
    second["candle"]["timestamp"] = "2024-01-01T01:00:00+00:00"
    second["candle"]["open"] = 102.0
    second["candle"]["high"] = 103.0
    second["candle"]["low"] = 101.0
    second["candle"]["close"] = 102.5
    second["strategy"]["timestamp"] = second["candle"]["timestamp"]
    second["risk"]["timestamp"] = second["candle"]["timestamp"]
    response = client.post("/paper/process", json=second)
    assert response.status_code == 200
    state = client.get("/paper/state").json()
    assert state["open_position"] is not None
    assert state["open_position"]["entry_timestamp"] == "2024-01-01T01:00:00Z"
    assert state["open_position"]["entry_price"] == pytest.approx(102.0 * 1.0005)
    reset = client.post("/paper/reset")
    assert reset.status_code == 200
    assert reset.json()["open_position"] is None
