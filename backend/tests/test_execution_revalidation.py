from datetime import datetime, timezone

import pytest

from backend.app.market.models import Candle
from backend.app.paper.models import PaperTradingConfig, PendingEntry
from backend.app.paper.service import PaperTradingService
from backend.app.risk.execution import ExecutionRiskRevalidationService
from backend.app.risk.models import RiskDecision, RiskPolicy
from backend.app.strategy.models import Assessment, StrategyResult

TS=datetime(2026,9,6,tzinfo=timezone.utc)


def account(*, fee:float=0.1, slippage:float=0.05):
    service=PaperTradingService(); acc=service.start(PaperTradingConfig(transaction_cost_pct=fee,slippage_pct=slippage)); acc.risk_day=TS.date().isoformat(); return acc


def candle(price:float)->Candle:
    return Candle(timestamp=TS,symbol="BTCUSDT",timeframe="1h",open=price,high=price+1,low=price-1,close=price,volume=1000.0)


def strategy()->StrategyResult:
    return StrategyResult(timestamp=TS,symbol="BTCUSDT",timeframe="1h",score=4,normalized_score=90,assessment=Assessment.BULLISH,data_ready=True,evidence=[])


def pending(*, quantity:float=1.0, stop:float=95.0)->PendingEntry:
    return PendingEntry(signal_timestamp=TS,symbol="BTCUSDT",timeframe="1h",assessment="BULLISH",execute_index=1,quantity=quantity,stop_loss_price=stop)


def test_all_in_execution_risk_formula_is_explicit_and_deterministic()->None:
    acc=account(fee=0.1,slippage=0.05)
    result=ExecutionRiskRevalidationService().evaluate(account=acc,candle=candle(100.0),strategy=strategy(),pending=pending(quantity=1.0,stop=95.0))
    assert result.estimate is not None
    expected_entry=100.0*1.0005
    expected_stop=95.0*0.9995
    expected_loss=(expected_entry-expected_stop)+(expected_entry*0.001)+(expected_stop*0.001)
    assert result.estimate.effective_entry_price==pytest.approx(expected_entry)
    assert result.estimate.estimated_stop_fill_price==pytest.approx(expected_stop)
    assert result.estimate.planned_all_in_loss==pytest.approx(expected_loss)
    assert result.estimate.risk_per_trade_pct==pytest.approx(expected_loss/10000.0*100.0)


def test_safe_next_open_gets_fresh_allow()->None:
    acc=account(fee=0.0,slippage=0.0)
    result=ExecutionRiskRevalidationService().evaluate(account=acc,candle=candle(100.0),strategy=strategy(),pending=pending(quantity=1.0,stop=95.0))
    assert result.allowed is True
    assert result.risk is not None and result.risk.decision==RiskDecision.ALLOW


def test_gap_up_can_turn_old_permission_into_block()->None:
    acc=account(fee=0.0,slippage=0.0)
    result=ExecutionRiskRevalidationService().evaluate(account=acc,candle=candle(200.0),strategy=strategy(),pending=pending(quantity=1.0,stop=95.0),policy=RiskPolicy(max_risk_per_trade_pct=1.0,warning_risk_per_trade_pct=0.75))
    assert result.allowed is False
    assert result.risk is not None and result.risk.decision==RiskDecision.BLOCK


def test_warning_is_not_execution_permission()->None:
    acc=account(fee=0.0,slippage=0.0)
    result=ExecutionRiskRevalidationService().evaluate(account=acc,candle=candle(180.0),strategy=strategy(),pending=pending(quantity=1.0,stop=95.0),policy=RiskPolicy(max_risk_per_trade_pct=1.0,warning_risk_per_trade_pct=0.75))
    assert result.allowed is False
    assert result.risk is not None and result.risk.decision==RiskDecision.WARNING


def test_missing_sized_fields_fail_closed()->None:
    acc=account()
    legacy=PendingEntry(signal_timestamp=TS,symbol="BTCUSDT",timeframe="1h",assessment="BULLISH",execute_index=1)
    result=ExecutionRiskRevalidationService().evaluate(account=acc,candle=candle(100.0),strategy=strategy(),pending=legacy)
    assert result.allowed is False
    assert result.risk is None


def test_invalid_stop_after_price_change_fails_closed()->None:
    acc=account(fee=0.0,slippage=0.0)
    result=ExecutionRiskRevalidationService().evaluate(account=acc,candle=candle(90.0),strategy=strategy(),pending=pending(quantity=1.0,stop=95.0))
    assert result.allowed is False
    assert result.risk is None


def test_insufficient_cash_fails_closed_without_resizing()->None:
    acc=account(fee=1.0,slippage=0.0)
    result=ExecutionRiskRevalidationService().evaluate(account=acc,candle=candle(100.0),strategy=strategy(),pending=pending(quantity=100.0,stop=95.0))
    assert result.allowed is False
    assert "cash" in result.reason.lower()


def test_unavailable_context_fails_closed()->None:
    acc=account(); acc.risk_day=None
    result=ExecutionRiskRevalidationService().evaluate(account=acc,candle=candle(100.0),strategy=strategy(),pending=pending())
    assert result.allowed is False
    assert result.context_availability is not None
    assert result.context_availability.available is False
