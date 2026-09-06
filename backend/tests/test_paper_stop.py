from datetime import datetime, timedelta, timezone

import pytest

from backend.app.market.models import Candle
from backend.app.paper.models import PaperExitReason, PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskDecision, RiskResult
from backend.app.strategy.models import Assessment, StrategyResult

BASE=datetime(2026,9,6,tzinfo=timezone.utc)


def candle(i:int,open_:float,low:float|None=None)->Candle:
    return Candle(timestamp=BASE+timedelta(hours=i),symbol="BTCUSDT",timeframe="1h",open=open_,high=open_+2,low=low if low is not None else open_-1,close=open_,volume=1000.0)


def strategy(i:int,assessment:Assessment=Assessment.BULLISH)->StrategyResult:
    return StrategyResult(timestamp=BASE+timedelta(hours=i),symbol="BTCUSDT",timeframe="1h",score=4,normalized_score=90,assessment=assessment,data_ready=True,evidence=[])


def risk(i:int,decision:RiskDecision=RiskDecision.ALLOW)->RiskResult:
    return RiskResult(timestamp=BASE+timedelta(hours=i),symbol="BTCUSDT",timeframe="1h",strategy_assessment="BULLISH",strategy_score=4,decision=decision,data_ready=True,evidence=[],block_reasons=[],warning_reasons=[])


def service(**kwargs)->PaperTradingService:
    s=PaperTradingService(); s.start(PaperTradingConfig(**kwargs)); return s


def open_with_stop(s:PaperTradingService,stop:float=95.0)->None:
    s.process_candle(candle(0,100),strategy(0),risk(0),stop_loss_price=stop)
    assert s.state().pending_entry is not None
    assert s.state().pending_entry.stop_loss_price==stop
    s.process_candle(candle(1,100,94),strategy(1),risk(1),stop_loss_price=stop)
    assert s.state().open_position is not None
    assert s.state().open_position.stop_loss_price==stop
    assert s.state().closed_trades==[]  # historical LOW on entry candle cannot stop a just-opened position


def test_stop_persists_and_no_same_candle_lookahead_stop()->None:
    open_with_stop(service(transaction_cost_pct=0.0,slippage_pct=0.0))


def test_carried_position_low_breach_fills_at_stop()->None:
    s=service(transaction_cost_pct=0.0,slippage_pct=0.0); open_with_stop(s)
    s.process_candle(candle(2,100,94),strategy(2),risk(2, RiskDecision.BLOCK))
    trade=s.state().closed_trades[0]
    assert trade.exit_reason==PaperExitReason.STOP_LOSS
    assert trade.exit_price==pytest.approx(95.0)
    assert s.state().open_position is None


def test_gap_through_uses_open_not_optimistic_stop()->None:
    s=service(transaction_cost_pct=0.0,slippage_pct=0.0); open_with_stop(s)
    s.process_candle(candle(2,90,89),strategy(2),risk(2, RiskDecision.BLOCK))
    trade=s.state().closed_trades[0]
    assert trade.exit_price==pytest.approx(90.0)
    assert trade.exit_price<95.0


def test_stop_charges_adverse_slippage_and_exit_fee()->None:
    s=service(transaction_cost_pct=1.0,slippage_pct=2.0); open_with_stop(s)
    s.process_candle(candle(2,100,94),strategy(2),risk(2, RiskDecision.BLOCK))
    trade=s.state().closed_trades[0]
    assert trade.exit_price==pytest.approx(95.0*0.98)
    assert trade.exit_transaction_cost==pytest.approx(trade.exit_notional*0.01)
    assert trade.net_pnl<trade.gross_pnl


def test_stop_is_reduce_risk_and_does_not_require_allow()->None:
    s=service(transaction_cost_pct=0.0,slippage_pct=0.0); open_with_stop(s)
    s.process_candle(candle(2,100,94),strategy(2),risk(2,RiskDecision.BLOCK))
    assert s.state().open_position is None
    assert s.state().closed_trades[0].exit_reason==PaperExitReason.STOP_LOSS


def test_stop_prevents_new_strategy_exit_scheduling_same_candle()->None:
    s=service(transaction_cost_pct=0.0,slippage_pct=0.0); open_with_stop(s)
    s.process_candle(candle(2,100,94),strategy(2,Assessment.BEARISH),risk(2,RiskDecision.BLOCK))
    assert s.state().open_position is None
    assert s.state().pending_exit is None
    assert len(s.state().closed_trades)==1


def test_existing_pending_strategy_exit_keeps_next_open_priority()->None:
    s=service(transaction_cost_pct=0.0,slippage_pct=0.0); open_with_stop(s)
    s.process_candle(candle(2,100,96),strategy(2,Assessment.BEARISH),risk(2))
    assert s.state().pending_exit is not None
    s.process_candle(candle(3,90,89),strategy(3,Assessment.BEARISH),risk(3,RiskDecision.BLOCK))
    trade=s.state().closed_trades[0]
    assert trade.exit_reason==PaperExitReason.STRATEGY
    assert trade.exit_price==pytest.approx(90.0)
