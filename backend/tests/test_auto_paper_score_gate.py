from datetime import datetime, timedelta, timezone

from backend.app.market.models import Candle
from backend.app.paper.auto_loop import AutoPaperLoopService
from backend.app.paper.models import PaperTradingConfig
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskDecision
from backend.app.strategy.models import Assessment, StrategyResult

TS = datetime(2026, 9, 8, tzinfo=timezone.utc)


def candles(count: int = 40) -> list[Candle]:
    return [
        Candle(
            timestamp=TS + timedelta(hours=i),
            symbol="BTCUSDT",
            timeframe="1h",
            open=100.0 + i * 0.4,
            high=101.2 + i * 0.4,
            low=99.0 + i * 0.4,
            close=100.5 + i * 0.4,
            volume=1000.0 + i,
        )
        for i in range(count)
    ]


def started_loop() -> AutoPaperLoopService:
    service = PaperTradingService()
    service.start(PaperTradingConfig(transaction_cost_pct=0.0, slippage_pct=0.0))
    return AutoPaperLoopService(service)


def force_score(loop: AutoPaperLoopService, monkeypatch, score: int) -> None:
    monkeypatch.setattr(loop.indicators, "build_snapshots", lambda values: values)
    assessment = (
        Assessment.BEARISH if score < 0
        else Assessment.NEUTRAL if score <= 1
        else Assessment.BULLISH
    )
    monkeypatch.setattr(
        loop.strategy,
        "build_results",
        lambda values: [
            StrategyResult(
                timestamp=values[-1].timestamp,
                symbol=values[-1].symbol,
                timeframe=values[-1].timeframe,
                score=score,
                normalized_score=50,
                assessment=assessment,
                data_ready=True,
                evidence=[],
            )
        ],
    )


def test_negative_score_blocks_buy_without_risk_proposal(monkeypatch) -> None:
    loop = started_loop()
    force_score(loop, monkeypatch, -1)
    result = loop.cycle(candles())
    assert result.entry is None
    assert result.account.pending_entry is None
    assert result.reason.startswith("BLOCK BUY:")


def test_score_zero_or_one_waits_without_risk_proposal(monkeypatch) -> None:
    for score in (0, 1):
        loop = started_loop()
        force_score(loop, monkeypatch, score)
        result = loop.cycle(candles())
        assert result.entry is None
        assert result.account.pending_entry is None
        assert result.reason.startswith("WAIT:")
        assert "0..1" in result.reason


def test_score_above_one_reaches_risk_guard_immediately(monkeypatch) -> None:
    loop = started_loop()
    force_score(loop, monkeypatch, 2)
    result = loop.cycle(candles())
    assert result.entry is not None
    assert result.authorization is result.entry
    assert result.entry.gate is not None
    assert result.entry.gate.risk is not None
    assert result.entry.gate.risk.decision in {
        RiskDecision.ALLOW,
        RiskDecision.WARNING,
        RiskDecision.BLOCK,
    }
    assert not result.reason.startswith("WAIT:")
