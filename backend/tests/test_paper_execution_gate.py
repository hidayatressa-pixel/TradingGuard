from datetime import datetime, timedelta, timezone

import pytest

from backend.app.market.models import Candle
from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskDecision, RiskPolicy, RiskResult
from backend.app.strategy.models import Assessment, StrategyResult

BASE=datetime(2026,9,6,tzinfo=timezone.utc)


def strategy(i:int)->StrategyResult:
    return StrategyResult(timestamp=BASE+timedelta(hours=i),symbol="BTCUSDT",timeframe="1h",score=4,normalized_score=90,assessment=Assessment.BULLISH,data_ready=True,evidence=[])


def risk(i:int,decision:RiskDecision=RiskDecision.ALLOW)->RiskResult:
    return RiskResult(timestamp=BASE+timedelta(hours=i),symbol="BTCUSDT",timeframe="1h",strategy_assessment="BULLISH",strategy_score=4,decision=decision,data_ready=True,evidence=[],block_reasons=[],warning_reasons=[])


def candle(i:int,price:float)->Candle:
    return Candle(timestamp=BASE+timedelta(hours=i),symbol="BTCUSDT",timeframe="1h",open=price,high=price+1,low=price-1,close=price,volume=1000.0)


def service()->PaperTradingService:
    result=PaperTradingService(); result.start(PaperTradingConfig(transaction_cost_pct=0.0,slippage_pct=0.0)); return result


def schedule(result:PaperTradingService,quantity:float=1.0,stop:float=95.0)->None:
    result.schedule_sized_entry(strategy=strategy(0),risk=risk(0),quantity=quantity,stop_loss_price=stop,expected_equity=10000.0)


def test_fresh_allow_executes_exact_sized_quantity()->None:
    result=service(); schedule(result,quantity=2.0)
    result.process_candle(candle(0,100.0),strategy(0),risk(0,RiskDecision.BLOCK))
    result.process_candle(candle(1,100.0),strategy(1),risk(1,RiskDecision.BLOCK))
    assert result.state().open_position is not None
    assert result.state().open_position.quantity==pytest.approx(2.0)


def test_gap_up_block_cancels_pending_buy_before_execution()->None:
    result=service(); schedule(result,quantity=1.0)
    result.process_candle(candle(0,100.0),strategy(0),risk(0,RiskDecision.BLOCK))
    result.process_candle(candle(1,200.0),strategy(1),risk(1,RiskDecision.ALLOW),execution_policy=RiskPolicy(max_risk_per_trade_pct=1.0,warning_risk_per_trade_pct=0.75))
    assert result.state().open_position is None
    assert result.state().pending_entry is None


def test_gap_up_warning_also_cancels_pending_buy()->None:
    result=service(); schedule(result,quantity=1.0)
    result.process_candle(candle(0,100.0),strategy(0),risk(0,RiskDecision.BLOCK))
    result.process_candle(candle(1,180.0),strategy(1),risk(1,RiskDecision.ALLOW),execution_policy=RiskPolicy(max_risk_per_trade_pct=1.0,warning_risk_per_trade_pct=0.75))
    assert result.state().open_position is None
    assert result.state().pending_entry is None


def test_fresh_gate_uses_current_strategy_not_stale_signal_risk()->None:
    result=service(); schedule(result,quantity=1.0)
    result.process_candle(candle(0,100.0),strategy(0),risk(0,RiskDecision.BLOCK))
    current=strategy(1).model_copy(update={"data_ready":False,"assessment":Assessment.INSUFFICIENT_DATA})
    result.process_candle(candle(1,100.0),current,risk(1,RiskDecision.ALLOW))
    assert result.state().open_position is None
    assert result.state().pending_entry is None


def test_public_legacy_process_does_not_schedule_buy_without_stop()->None:
    result=service()
    result.process_candle(candle(0,100.0),strategy(0),risk(0,RiskDecision.ALLOW))
    assert result.state().pending_entry is None
    assert result.state().open_position is None
