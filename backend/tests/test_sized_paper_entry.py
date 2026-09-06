from datetime import datetime, timedelta, timezone

import pytest

from backend.app.market.models import Candle
from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskDecision, RiskResult
from backend.app.strategy.models import Assessment, StrategyResult

BASE=datetime(2026,9,6,tzinfo=timezone.utc)


def strategy(i:int=0)->StrategyResult:
    return StrategyResult(timestamp=BASE+timedelta(hours=i),symbol="BTCUSDT",timeframe="1h",score=4,normalized_score=90,assessment=Assessment.BULLISH,data_ready=True,evidence=[])


def risk(i:int=0,decision:RiskDecision=RiskDecision.ALLOW)->RiskResult:
    return RiskResult(timestamp=BASE+timedelta(hours=i),symbol="BTCUSDT",timeframe="1h",strategy_assessment="BULLISH",strategy_score=4,decision=decision,data_ready=True,evidence=[],block_reasons=[],warning_reasons=[])


def candle(i:int,price:float=100.0)->Candle:
    return Candle(timestamp=BASE+timedelta(hours=i),symbol="BTCUSDT",timeframe="1h",open=price,high=price+1,low=price-1,close=price,volume=1000.0)


def started(**kwargs)->PaperTradingService:
    service=PaperTradingService(); service.start(PaperTradingConfig(**kwargs)); return service


def execute_due_entry(service:PaperTradingService)->None:
    service.process_candle(candle(0),strategy(0,Assessment.NEUTRAL) if False else strategy(0),risk(0,RiskDecision.BLOCK))
    service.process_candle(candle(1),strategy(1),risk(1,RiskDecision.BLOCK))


def test_sized_entry_executes_exact_authoritative_quantity()->None:
    service=started(position_size_pct=1.0,transaction_cost_pct=0.0,slippage_pct=0.0)
    service.schedule_sized_entry(strategy=strategy(),risk=risk(),quantity=12.5,stop_loss_price=95.0,expected_equity=10000.0)
    service.process_candle(candle(0),strategy(0),risk(0,RiskDecision.BLOCK))
    service.process_candle(candle(1),strategy(1),risk(1,RiskDecision.BLOCK))
    assert service.state().open_position is not None
    assert service.state().open_position.quantity==pytest.approx(12.5)
    assert service.state().open_position.stop_loss_price==pytest.approx(95.0)


def test_sized_entry_does_not_recalculate_from_position_size_pct()->None:
    service=started(position_size_pct=1.0,transaction_cost_pct=0.0,slippage_pct=0.0)
    service.schedule_sized_entry(strategy=strategy(),risk=risk(),quantity=5.0,stop_loss_price=95.0,expected_equity=10000.0)
    service.process_candle(candle(0),strategy(0),risk(0,RiskDecision.BLOCK))
    service.process_candle(candle(1),strategy(1),risk(1,RiskDecision.BLOCK))
    assert service.state().open_position.quantity==pytest.approx(5.0)
    assert service.state().open_position.entry_notional==pytest.approx(500.0)


def test_stale_sizing_equity_fails_closed()->None:
    service=started()
    with pytest.raises(ValueError,match="stale"):
        service.schedule_sized_entry(strategy=strategy(),risk=risk(),quantity=1.0,stop_loss_price=95.0,expected_equity=9999.0)
    assert service.state().pending_entry is None


@pytest.mark.parametrize("decision",[RiskDecision.WARNING,RiskDecision.BLOCK])
def test_non_allow_cannot_schedule_sized_entry(decision:RiskDecision)->None:
    service=started()
    with pytest.raises(ValueError,match="ALLOW"):
        service.schedule_sized_entry(strategy=strategy(),risk=risk(decision=decision),quantity=1.0,stop_loss_price=95.0,expected_equity=10000.0)
    assert service.state().pending_entry is None


def test_insufficient_cash_fails_closed_without_resizing()->None:
    service=started(transaction_cost_pct=1.0,slippage_pct=0.0)
    service.schedule_sized_entry(strategy=strategy(),risk=risk(),quantity=100.0,stop_loss_price=95.0,expected_equity=10000.0)
    with pytest.raises(ValueError,match="silently resized"):
        service.process_candle(candle(0),strategy(0),risk(0,RiskDecision.BLOCK))
    assert service.state().open_position is None


def test_sized_entry_keeps_next_event_timing()->None:
    service=started(transaction_cost_pct=0.0,slippage_pct=0.0)
    service.schedule_sized_entry(strategy=strategy(),risk=risk(),quantity=2.0,stop_loss_price=95.0,expected_equity=10000.0)
    assert service.state().open_position is None
    assert service.state().pending_entry.execute_index==1
    service.process_candle(candle(0),strategy(0),risk(0,RiskDecision.BLOCK))
    assert service.state().open_position is None
    service.process_candle(candle(1),strategy(1),risk(1,RiskDecision.BLOCK))
    assert service.state().open_position is not None
