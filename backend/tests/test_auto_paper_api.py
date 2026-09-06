from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.main import app, auto_paper_loop, paper_service
from backend.app.market.models import Candle
from backend.app.paper.auto_loop import AutoPaperCycleResult
from backend.app.paper.orchestration import AutoPaperEntryResult
from backend.app.risk.models import RiskDecision, RiskResult
from backend.app.risk_sizing.models import ProspectiveRiskGateResult, RiskSizingResult
from backend.app.strategy.models import Assessment, StrategyResult

client = TestClient(app)
TS = datetime(2026, 9, 6, tzinfo=timezone.utc)


def setup_function() -> None:
    paper_service.reset()


def start_paper() -> None:
    response = client.post("/paper/start", json={"config": {"transaction_cost_pct": 0.0, "slippage_pct": 0.0}})
    assert response.status_code == 200
    paper_service.state().risk_day = "2026-09-06"


def candles(count: int = 40) -> list[Candle]:
    result = []
    for i in range(count):
        base = 100.0 + i * 0.4
        result.append(Candle(
            timestamp=TS + timedelta(hours=i), symbol="BTCUSDT", timeframe="1h",
            open=base, high=base + 1.2, low=base - 1.0, close=base + 0.5,
            volume=1000.0 + i,
        ))
    return result


def bullish_strategy() -> StrategyResult:
    return StrategyResult(
        timestamp=TS, symbol="BTCUSDT", timeframe="1h", score=4,
        normalized_score=90, assessment=Assessment.BULLISH, data_ready=True,
        evidence=[],
    )


def risk_result(decision: RiskDecision) -> RiskResult:
    return RiskResult(
        timestamp=TS, symbol="BTCUSDT", timeframe="1h",
        strategy_assessment="BULLISH", strategy_score=4, decision=decision,
        data_ready=True, evidence=[], block_reasons=[], warning_reasons=[],
    )


def sizing(risk_pct: float) -> RiskSizingResult:
    return RiskSizingResult(
        equity=10000.0, reference_entry_price=100.0, stop_loss_price=95.0,
        requested_risk_budget_pct=risk_pct, requested_risk_budget_amount=10000.0 * risk_pct / 100.0,
        stop_distance=5.0, stop_distance_pct=5.0,
        quantity_by_risk=10.0, notional_by_risk=1000.0,
        max_allocation_pct=20.0, max_allocation_amount=2000.0,
        quantity_by_allocation=20.0, allocation_cap_applied=False,
        final_quantity=10.0, final_notional=1000.0,
        risk_amount=50.0, risk_per_trade_pct=risk_pct, allocation_pct=10.0,
        costs_included_in_risk=False, cost_treatment="excluded",
    )


def cycle_result(decision: RiskDecision, *, scheduled: bool) -> AutoPaperCycleResult:
    gate = ProspectiveRiskGateResult(
        sizing=sizing(0.5 if decision == RiskDecision.ALLOW else 0.8),
        context_availability={
            "available": True,
            "context": {
                "risk_per_trade_pct": 0.5,
                "daily_loss_pct": 0.0,
                "total_exposure_pct": 10.0,
                "open_positions": 0,
                "current_drawdown_pct": 0.0,
                "trading_enabled": True,
            },
            "missing_facts": [],
            "reason": "Complete authoritative RiskContext is available.",
        },
        risk=risk_result(decision),
        execution_permission_established=scheduled,
        reason="test gate",
    )
    entry = AutoPaperEntryResult(
        scheduled=scheduled,
        execution_permission_established=scheduled,
        gate=gate,
        auto_stop=None,
        reason="test entry",
    )
    return AutoPaperCycleResult(strategy=bullish_strategy(), entry=entry, account=paper_service.state(), reason="test cycle")


def test_auto_cycle_api_uses_server_derived_market_inputs(monkeypatch) -> None:
    start_paper()
    seen: dict[str, object] = {}

    def fake_candles(source: str, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        seen.update(source=source, symbol=symbol, timeframe=timeframe, limit=limit)
        return candles()

    def fake_cycle(authoritative_candles: list[Candle], **kwargs: object) -> AutoPaperCycleResult:
        seen["candles"] = authoritative_candles
        seen.update(kwargs)
        return cycle_result(RiskDecision.ALLOW, scheduled=True)

    monkeypatch.setattr("backend.app.main._candles", fake_candles)
    monkeypatch.setattr(auto_paper_loop, "cycle", fake_cycle)
    response = client.post("/paper/auto-cycle?symbol=BTCUSDT&timeframe=1h&source=binance&risk_budget_pct=0.5&max_allocation_pct=20")
    assert response.status_code == 200
    assert response.json()["entry"]["gate"]["risk"]["decision"] == "ALLOW"
    assert seen["source"] == "binance"
    assert seen["symbol"] == "BTCUSDT"
    assert seen["timeframe"] == "1h"
    assert seen["risk_budget_pct"] == 0.5
    assert seen["max_allocation_pct"] == 20.0


def test_auto_cycle_api_warning_does_not_claim_execution_permission(monkeypatch) -> None:
    start_paper()
    monkeypatch.setattr("backend.app.main._candles", lambda *args, **kwargs: candles())
    monkeypatch.setattr(auto_paper_loop, "cycle", lambda *args, **kwargs: cycle_result(RiskDecision.WARNING, scheduled=False))
    response = client.post("/paper/auto-cycle?symbol=BTCUSDT&timeframe=1h&source=binance&risk_budget_pct=0.8")
    assert response.status_code == 200
    body = response.json()
    assert body["entry"]["scheduled"] is False
    assert body["entry"]["execution_permission_established"] is False
    assert body["entry"]["gate"]["risk"]["decision"] == "WARNING"


def test_auto_cycle_api_rejects_invalid_risk_budget_before_pipeline() -> None:
    start_paper()
    response = client.post("/paper/auto-cycle?symbol=BTCUSDT&timeframe=1h&source=binance&risk_budget_pct=1.5")
    assert response.status_code == 422


def test_auto_cycle_api_fails_closed_when_paper_inactive(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.main._candles", lambda *args, **kwargs: candles())
    response = client.post("/paper/auto-cycle?symbol=BTCUSDT&timeframe=1h&source=binance")
    assert response.status_code == 422
    assert paper_service.state().pending_entry is None
