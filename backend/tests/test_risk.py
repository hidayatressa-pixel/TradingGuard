from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.risk.models import RiskContext, RiskDecision, RiskPolicy
from backend.app.risk.service import RiskService
from backend.app.strategy.models import Assessment, StrategyEvidence, StrategyResult

client = TestClient(app)


def build_strategy(score: int = 5, assessment: Assessment = Assessment.STRONG_BULLISH) -> StrategyResult:
    return StrategyResult(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        score=score,
        normalized_score=100 if score >= 0 else 0,
        assessment=assessment,
        data_ready=True,
        evidence=[
            StrategyEvidence(
                indicator="EMA",
                condition="ema_fast > ema_slow",
                contribution=2,
                description="Fast EMA is above slow EMA.",
            )
        ],
    )


def test_risk_policy_validation() -> None:
    with pytest.raises(ValidationError):
        RiskPolicy(warning_risk_per_trade_pct=1.1, max_risk_per_trade_pct=1.0)

    with pytest.raises(ValidationError):
        RiskPolicy(warning_daily_loss_pct=4.0, max_daily_loss_pct=3.0)

    with pytest.raises(ValidationError):
        RiskPolicy(warning_total_exposure_pct=30.0, max_total_exposure_pct=20.0)

    with pytest.raises(ValidationError):
        RiskPolicy(warning_open_positions=4, max_open_positions=3)

    with pytest.raises(ValidationError):
        RiskPolicy(warning_drawdown_pct=12.0, max_drawdown_pct=10.0)

    with pytest.raises(ValidationError):
        RiskPolicy(max_risk_per_trade_pct=0)

    RiskPolicy()


def test_risk_context_validation() -> None:
    ctx = RiskContext(
        risk_per_trade_pct=0.5,
        daily_loss_pct=2.0,
        total_exposure_pct=12.0,
        open_positions=2,
        current_drawdown_pct=6.0,
    )
    assert ctx.trading_enabled is True

    with pytest.raises(ValidationError):
        RiskContext(
            risk_per_trade_pct=-0.1,
            daily_loss_pct=0.0,
            total_exposure_pct=0.0,
            open_positions=0,
            current_drawdown_pct=0.0,
        )


def test_manual_kill_switch_blocks() -> None:
    strategy = build_strategy(score=5, assessment=Assessment.STRONG_BULLISH)
    context = RiskContext(
        risk_per_trade_pct=0.2,
        daily_loss_pct=0.5,
        total_exposure_pct=5.0,
        open_positions=1,
        current_drawdown_pct=2.0,
        trading_enabled=False,
    )

    result = RiskService().evaluate(strategy, context, RiskPolicy())
    assert result.decision == RiskDecision.BLOCK
    assert any("manual kill switch" in reason.lower() for reason in result.block_reasons)


def test_incomplete_strategy_blocks() -> None:
    strategy = StrategyResult(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        score=0,
        normalized_score=50,
        assessment=Assessment.INSUFFICIENT_DATA,
        data_ready=False,
        evidence=[],
    )
    context = RiskContext(
        risk_per_trade_pct=0.2,
        daily_loss_pct=0.5,
        total_exposure_pct=5.0,
        open_positions=1,
        current_drawdown_pct=2.0,
    )

    result = RiskService().evaluate(strategy, context, RiskPolicy())
    assert result.decision == RiskDecision.BLOCK
    assert any("required strategy data" in reason.lower() for reason in result.block_reasons)


def test_risk_per_trade_boundaries() -> None:
    policy = RiskPolicy()

    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.74, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=0, current_drawdown_pct=0.0), policy).decision == RiskDecision.ALLOW
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.75, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=0, current_drawdown_pct=0.0), policy).decision == RiskDecision.WARNING
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=1.00, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=0, current_drawdown_pct=0.0), policy).decision == RiskDecision.WARNING
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=1.01, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=0, current_drawdown_pct=0.0), policy).decision == RiskDecision.BLOCK


def test_daily_loss_boundaries() -> None:
    policy = RiskPolicy()
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=1.99, total_exposure_pct=0.0, open_positions=0, current_drawdown_pct=0.0), policy).decision == RiskDecision.ALLOW
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=2.00, total_exposure_pct=0.0, open_positions=0, current_drawdown_pct=0.0), policy).decision == RiskDecision.WARNING
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=2.99, total_exposure_pct=0.0, open_positions=0, current_drawdown_pct=0.0), policy).decision == RiskDecision.WARNING
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=3.00, total_exposure_pct=0.0, open_positions=0, current_drawdown_pct=0.0), policy).decision == RiskDecision.BLOCK
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=3.01, total_exposure_pct=0.0, open_positions=0, current_drawdown_pct=0.0), policy).decision == RiskDecision.BLOCK


def test_exposure_position_and_drawdown_boundaries() -> None:
    policy = RiskPolicy()

    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=14.99, open_positions=1, current_drawdown_pct=7.49), policy).decision == RiskDecision.ALLOW
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=15.00, open_positions=1, current_drawdown_pct=7.49), policy).decision == RiskDecision.WARNING
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=20.00, open_positions=1, current_drawdown_pct=7.49), policy).decision == RiskDecision.WARNING
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=20.01, open_positions=1, current_drawdown_pct=7.49), policy).decision == RiskDecision.BLOCK

    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=1, current_drawdown_pct=7.49), policy).decision == RiskDecision.ALLOW
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=2, current_drawdown_pct=7.49), policy).decision == RiskDecision.WARNING
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=3, current_drawdown_pct=7.49), policy).decision == RiskDecision.BLOCK

    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=1, current_drawdown_pct=7.49), policy).decision == RiskDecision.ALLOW
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=1, current_drawdown_pct=7.50), policy).decision == RiskDecision.WARNING
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=1, current_drawdown_pct=9.99), policy).decision == RiskDecision.WARNING
    assert RiskService().evaluate(build_strategy(), RiskContext(risk_per_trade_pct=0.0, daily_loss_pct=0.0, total_exposure_pct=0.0, open_positions=1, current_drawdown_pct=10.00), policy).decision == RiskDecision.BLOCK


def test_strategy_result_is_strict() -> None:
    with pytest.raises(ValidationError):
        StrategyResult.model_validate({
            "timestamp": "2024-01-01T00:00:00Z",
            "symbol": "BTCUSD",
            "timeframe": "1h",
            "score": 5,
            "normalized_score": 100,
            "assessment": "STRONG_BULLISH",
            "data_ready": True,
            "evidence": [{
                "indicator": "EMA",
                "condition": "ema_fast > ema_slow",
                "contribution": 2,
                "description": "Fast EMA is above slow EMA.",
            }],
        })

    with pytest.raises(ValidationError):
        StrategyEvidence.model_validate({
            "indicator": 123,
            "condition": "ema_fast > ema_slow",
            "contribution": 2,
            "description": "Fast EMA is above slow EMA.",
        })


def test_multiple_block_and_warning_reasons() -> None:
    strategy = build_strategy(score=5, assessment=Assessment.STRONG_BULLISH)
    context = RiskContext(
        risk_per_trade_pct=1.02,
        daily_loss_pct=3.0,
        total_exposure_pct=21.0,
        open_positions=3,
        current_drawdown_pct=10.0,
    )
    result = RiskService().evaluate(strategy, context, RiskPolicy())
    assert result.decision == RiskDecision.BLOCK
    assert len(result.block_reasons) >= 3
    assert any("risk per trade" in reason.lower() for reason in result.block_reasons)
    assert any("daily loss" in reason.lower() for reason in result.block_reasons)

    warning_only = RiskContext(
        risk_per_trade_pct=0.75,
        daily_loss_pct=2.0,
        total_exposure_pct=15.0,
        open_positions=2,
        current_drawdown_pct=7.5,
    )
    warning_result = RiskService().evaluate(strategy, warning_only, RiskPolicy())
    assert warning_result.decision == RiskDecision.WARNING
    assert len(warning_result.warning_reasons) >= 3


def test_block_overrides_warning_and_strategy_strength() -> None:
    strong_bullish = build_strategy(score=5, assessment=Assessment.STRONG_BULLISH)
    strong_bearish = build_strategy(score=-5, assessment=Assessment.STRONG_BEARISH)

    context = RiskContext(
        risk_per_trade_pct=1.02,
        daily_loss_pct=0.0,
        total_exposure_pct=0.0,
        open_positions=0,
        current_drawdown_pct=0.0,
    )

    assert RiskService().evaluate(strong_bullish, context, RiskPolicy()).decision == RiskDecision.BLOCK
    assert RiskService().evaluate(strong_bearish, context, RiskPolicy()).decision == RiskDecision.BLOCK


def test_risk_result_keeps_strategy_values_and_does_not_mutate_inputs() -> None:
    strategy = build_strategy(score=5, assessment=Assessment.STRONG_BULLISH)
    context = RiskContext(
        risk_per_trade_pct=0.2,
        daily_loss_pct=0.5,
        total_exposure_pct=5.0,
        open_positions=1,
        current_drawdown_pct=2.0,
    )
    policy = RiskPolicy()

    result = RiskService().evaluate(strategy, context, policy)

    assert result.timestamp == strategy.timestamp
    assert result.symbol == strategy.symbol
    assert result.timeframe == strategy.timeframe
    assert result.strategy_assessment == strategy.assessment
    assert result.strategy_score == strategy.score
    assert strategy.assessment == Assessment.STRONG_BULLISH
    assert context.risk_per_trade_pct == 0.2
    assert policy.max_risk_per_trade_pct == 1.0


def test_risk_decision_is_derivable_from_evidence() -> None:
    strategy = build_strategy(score=2, assessment=Assessment.BULLISH)
    context = RiskContext(risk_per_trade_pct=0.8, daily_loss_pct=1.0, total_exposure_pct=10.0, open_positions=1, current_drawdown_pct=5.0)
    result = RiskService().evaluate(strategy, context, RiskPolicy())
    assert result.decision == RiskDecision.WARNING
    assert any(item.status == "WARNING" for item in result.evidence)
    assert not any(item.status == "BLOCK" for item in result.evidence)


def test_strategy_direction_does_not_control_risk() -> None:
    bullish = build_strategy(score=5, assessment=Assessment.STRONG_BULLISH)
    bearish = build_strategy(score=-5, assessment=Assessment.STRONG_BEARISH)
    neutral = build_strategy(score=0, assessment=Assessment.NEUTRAL)

    context = RiskContext(risk_per_trade_pct=0.2, daily_loss_pct=0.5, total_exposure_pct=5.0, open_positions=1, current_drawdown_pct=2.0)

    assert RiskService().evaluate(bullish, context, RiskPolicy()).decision == RiskDecision.ALLOW
    assert RiskService().evaluate(bearish, context, RiskPolicy()).decision == RiskDecision.ALLOW
    assert RiskService().evaluate(neutral, context, RiskPolicy()).decision == RiskDecision.ALLOW


def test_risk_api_evaluate() -> None:
    payload = {
        "strategy": {
            "timestamp": "2024-01-01T00:00:00Z",
            "symbol": "BTCUSD",
            "timeframe": "1h",
            "score": 5,
            "normalized_score": 100,
            "assessment": "STRONG_BULLISH",
            "data_ready": True,
            "evidence": [
                {
                    "indicator": "EMA",
                    "condition": "ema_fast > ema_slow",
                    "contribution": 2,
                    "description": "Fast EMA is above slow EMA.",
                }
            ],
        },
        "context": {
            "risk_per_trade_pct": 0.2,
            "daily_loss_pct": 0.5,
            "total_exposure_pct": 5.0,
            "open_positions": 1,
            "current_drawdown_pct": 2.0,
            "trading_enabled": True,
        },
        "policy": {
            "max_risk_per_trade_pct": 1.0,
            "warning_risk_per_trade_pct": 0.75,
            "max_daily_loss_pct": 3.0,
            "warning_daily_loss_pct": 2.0,
            "max_total_exposure_pct": 20.0,
            "warning_total_exposure_pct": 15.0,
            "max_open_positions": 3,
            "warning_open_positions": 2,
            "max_drawdown_pct": 10.0,
            "warning_drawdown_pct": 7.5,
        },
    }

    response = client.post("/risk/evaluate", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["decision"] == "ALLOW"
    assert result["strategy_assessment"] == "STRONG_BULLISH"

    invalid = client.post("/risk/evaluate", json={"strategy": {"score": 1}, "context": {}})
    assert invalid.status_code == 422


def test_existing_endpoints_still_work() -> None:
    health = client.get("/health")
    assert health.status_code == 200

    market = client.get("/market/candles", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 2})
    assert market.status_code == 200

    indicators = client.get("/indicators", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 2})
    assert indicators.status_code == 200

    strategy = client.get("/strategy", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 5})
    assert strategy.status_code == 200
