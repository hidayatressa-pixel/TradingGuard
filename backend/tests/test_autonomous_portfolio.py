from datetime import datetime, timedelta, timezone

from backend.app.market.models import Candle
from backend.app.paper.autonomous_portfolio import AutonomousPortfolioService
from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskPolicy
from backend.app.strategy.models import Assessment, StrategyResult


def candles(symbol: str = "BTCUSDT", count: int = 40) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result=[]
    for i in range(count):
        price=100.0+i
        result.append(Candle(timestamp=start+timedelta(minutes=i),symbol=symbol,timeframe="1m",open=price,high=price+2,low=price-2,close=price+1,volume=1000.0))
    return result


def strategy(symbol: str = "BTCUSDT", assessment: Assessment = Assessment.STRONG_BULLISH) -> StrategyResult:
    return StrategyResult(timestamp=datetime(2026,1,1,1,0,tzinfo=timezone.utc),symbol=symbol,timeframe="1m",score=4,normalized_score=90,assessment=assessment,data_ready=True,evidence=[])


def service() -> tuple[PaperTradingService, AutonomousPortfolioService]:
    paper=PaperTradingService(); paper.start(PaperTradingConfig())
    return paper,AutonomousPortfolioService(paper)


def test_autonomous_portfolio_executes_only_after_risk_allow():
    paper,engine=service(); data=candles(); result=engine.cycle(completed_candles=data,strategy=strategy(),market_price=data[-1].close,risk_budget_pct=0.5,max_allocation_pct=10.0)
    assert result.executed is True
    assert result.decision == "ALLOW"
    assert result.gate is not None and result.gate.execution_permission_established is True
    assert paper.state().position_for("BTCUSDT") is not None


def test_autonomous_portfolio_warning_is_not_executed():
    paper,engine=service(); first=candles("BTCUSDT"); engine.cycle(completed_candles=first,strategy=strategy("BTCUSDT"),market_price=first[-1].close,risk_budget_pct=0.5,max_allocation_pct=10.0)
    second=candles("ETHUSDT"); result=engine.cycle(completed_candles=second,strategy=strategy("ETHUSDT"),market_price=second[-1].close,risk_budget_pct=0.5,max_allocation_pct=10.0,policy=RiskPolicy(warning_open_positions=1,max_open_positions=3))
    assert result.executed is False
    assert result.decision == "WARNING"
    assert result.gate is not None
    assert any(item.rule == "open_positions" and item.status.value == "WARNING" for item in result.gate.risk.evidence)
    assert paper.state().position_for("ETHUSDT") is None


def test_autonomous_portfolio_supports_different_symbols_when_guard_allows():
    paper,engine=service(); policy=RiskPolicy(warning_open_positions=3,max_open_positions=4,warning_total_exposure_pct=30.0,max_total_exposure_pct=40.0)
    first=candles("BTCUSDT"); second=candles("ETHUSDT")
    a=engine.cycle(completed_candles=first,strategy=strategy("BTCUSDT"),market_price=first[-1].close,risk_budget_pct=0.5,max_allocation_pct=10.0,policy=policy)
    b=engine.cycle(completed_candles=second,strategy=strategy("ETHUSDT"),market_price=second[-1].close,risk_budget_pct=0.5,max_allocation_pct=10.0,policy=policy)
    assert a.executed and b.executed
    assert {p.symbol for p in paper.state().open_positions} == {"BTCUSDT","ETHUSDT"}


def test_autonomous_portfolio_does_not_buy_non_bullish_setup():
    paper,engine=service(); data=candles(); result=engine.cycle(completed_candles=data,strategy=strategy(assessment=Assessment.NEUTRAL),market_price=data[-1].close)
    assert result.executed is False
    assert result.action == "HOLD"
    assert paper.state().open_positions == []
