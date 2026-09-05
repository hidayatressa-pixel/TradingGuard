from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.indicators.models import IndicatorSnapshot
from backend.app.main import app
from backend.app.strategy.models import Assessment
from backend.app.strategy.service import StrategyService

client = TestClient(app)


@pytest.fixture
def snapshot_bullish() -> IndicatorSnapshot:
    return IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=110.0,
        ema_slow=105.0,
        rsi=75.0,
        macd=2.0,
        macd_signal=1.0,
        macd_histogram=1.0,
    )


@pytest.fixture
def snapshot_bearish() -> IndicatorSnapshot:
    return IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=95.0,
        ema_slow=100.0,
        rsi=25.0,
        macd=1.0,
        macd_signal=2.0,
        macd_histogram=-1.0,
    )


def test_ema_bullish_contribution(snapshot_bullish: IndicatorSnapshot) -> None:
    result = StrategyService().evaluate_snapshot(snapshot_bullish)
    assert any(item.indicator == "EMA" and item.contribution == 2 for item in result.evidence)


def test_ema_bearish_contribution(snapshot_bearish: IndicatorSnapshot) -> None:
    result = StrategyService().evaluate_snapshot(snapshot_bearish)
    assert any(item.indicator == "EMA" and item.contribution == -2 for item in result.evidence)


def test_ema_equality_contribution() -> None:
    snapshot = IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=101.0,
        ema_slow=101.0,
        rsi=50.0,
        macd=1.0,
        macd_signal=1.0,
        macd_histogram=0.0,
    )
    result = StrategyService().evaluate_snapshot(snapshot)
    assert any(item.indicator == "EMA" and item.contribution == 0 for item in result.evidence)


def test_rsi_threshold_rules() -> None:
    bullish = IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=101.0,
        ema_slow=100.0,
        rsi=75.0,
        macd=1.0,
        macd_signal=1.0,
        macd_histogram=0.0,
    )
    bearish = IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=100.0,
        ema_slow=101.0,
        rsi=25.0,
        macd=1.0,
        macd_signal=1.0,
        macd_histogram=0.0,
    )
    neutral = IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=100.0,
        ema_slow=100.0,
        rsi=50.0,
        macd=1.0,
        macd_signal=1.0,
        macd_histogram=0.0,
    )

    assert StrategyService().evaluate_snapshot(bullish).evidence[1].contribution == -1
    assert StrategyService().evaluate_snapshot(bearish).evidence[1].contribution == 1
    assert StrategyService().evaluate_snapshot(neutral).evidence[1].contribution == 0


def test_macd_evidence_rules() -> None:
    bullish = IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=110.0,
        ema_slow=100.0,
        rsi=50.0,
        macd=2.0,
        macd_signal=1.0,
        macd_histogram=1.0,
    )
    bearish = IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=100.0,
        ema_slow=110.0,
        rsi=50.0,
        macd=1.0,
        macd_signal=2.0,
        macd_histogram=-1.0,
    )
    neutral = IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=100.0,
        ema_slow=100.0,
        rsi=50.0,
        macd=1.0,
        macd_signal=1.0,
        macd_histogram=0.0,
    )

    assert StrategyService().evaluate_snapshot(bullish).evidence[2].contribution == 2
    assert StrategyService().evaluate_snapshot(bearish).evidence[2].contribution == -2
    assert StrategyService().evaluate_snapshot(neutral).evidence[2].contribution == 0


def test_score_equals_sum_of_evidence_contributions() -> None:
    bullish = StrategyService().evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=110.0,
            ema_slow=100.0,
            rsi=80.0,
            macd=2.0,
            macd_signal=1.0,
            macd_histogram=1.0,
        )
    )
    bearish = StrategyService().evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=90.0,
            ema_slow=100.0,
            rsi=20.0,
            macd=0.0,
            macd_signal=2.0,
            macd_histogram=-2.0,
        )
    )
    neutral = StrategyService().evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=100.0,
            ema_slow=100.0,
            rsi=50.0,
            macd=1.0,
            macd_signal=1.0,
            macd_histogram=0.0,
        )
    )
    mixed = StrategyService().evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, 3, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=110.0,
            ema_slow=100.0,
            rsi=30.0,
            macd=1.0,
            macd_signal=2.0,
            macd_histogram=-1.0,
        )
    )

    assert bullish.score == sum(item.contribution for item in bullish.evidence)
    assert bearish.score == sum(item.contribution for item in bearish.evidence)
    assert neutral.score == sum(item.contribution for item in neutral.evidence)
    assert mixed.score == sum(item.contribution for item in mixed.evidence)


def test_raw_score_and_normalization_bounds() -> None:
    service = StrategyService()

    score_min = service.evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=90.0,
            ema_slow=100.0,
            rsi=90.0,
            macd=0.0,
            macd_signal=2.0,
            macd_histogram=-2.0,
        )
    )
    score_max = service.evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=110.0,
            ema_slow=100.0,
            rsi=10.0,
            macd=2.0,
            macd_signal=0.0,
            macd_histogram=2.0,
        )
    )
    score_mid = service.evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=100.0,
            ema_slow=100.0,
            rsi=50.0,
            macd=0.0,
            macd_signal=0.0,
            macd_histogram=0.0,
        )
    )

    assert score_min.score == -5
    assert score_max.score == 5
    assert score_mid.score == 0
    assert score_min.normalized_score == 0
    assert score_mid.normalized_score == 50
    assert score_max.normalized_score == 100
    assert 0 <= score_min.normalized_score <= 100
    assert 0 <= score_mid.normalized_score <= 100
    assert 0 <= score_max.normalized_score <= 100


@pytest.mark.parametrize(
    ("raw_score", "expected_assessment", "snapshot"),
    [
        (
            -5,
            Assessment.STRONG_BEARISH,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=90.0,
                ema_slow=100.0,
                rsi=90.0,
                macd=0.0,
                macd_signal=2.0,
                macd_histogram=-2.0,
            ),
        ),
        (
            -4,
            Assessment.STRONG_BEARISH,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=90.0,
                ema_slow=100.0,
                rsi=50.0,
                macd=0.0,
                macd_signal=2.0,
                macd_histogram=-2.0,
            ),
        ),
        (
            -3,
            Assessment.BEARISH,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=90.0,
                ema_slow=100.0,
                rsi=90.0,
                macd=1.0,
                macd_signal=1.0,
                macd_histogram=0.0,
            ),
        ),
        (
            -2,
            Assessment.BEARISH,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, 3, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=90.0,
                ema_slow=100.0,
                rsi=50.0,
                macd=1.0,
                macd_signal=1.0,
                macd_histogram=0.0,
            ),
        ),
        (
            -1,
            Assessment.NEUTRAL,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, 4, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=100.0,
                ema_slow=100.0,
                rsi=90.0,
                macd=1.0,
                macd_signal=1.0,
                macd_histogram=0.0,
            ),
        ),
        (
            0,
            Assessment.NEUTRAL,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, 5, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=100.0,
                ema_slow=100.0,
                rsi=50.0,
                macd=1.0,
                macd_signal=1.0,
                macd_histogram=0.0,
            ),
        ),
        (
            1,
            Assessment.NEUTRAL,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, 6, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=100.0,
                ema_slow=100.0,
                rsi=30.0,
                macd=1.0,
                macd_signal=1.0,
                macd_histogram=0.0,
            ),
        ),
        (
            2,
            Assessment.BULLISH,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, 7, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=110.0,
                ema_slow=100.0,
                rsi=50.0,
                macd=1.0,
                macd_signal=1.0,
                macd_histogram=0.0,
            ),
        ),
        (
            3,
            Assessment.BULLISH,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, 8, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=110.0,
                ema_slow=100.0,
                rsi=30.0,
                macd=1.0,
                macd_signal=1.0,
                macd_histogram=0.0,
            ),
        ),
        (
            4,
            Assessment.STRONG_BULLISH,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, 9, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=110.0,
                ema_slow=100.0,
                rsi=50.0,
                macd=2.0,
                macd_signal=1.0,
                macd_histogram=1.0,
            ),
        ),
        (
            5,
            Assessment.STRONG_BULLISH,
            IndicatorSnapshot(
                timestamp=datetime(2024, 1, 1, 10, tzinfo=timezone.utc),
                symbol="BTCUSD",
                timeframe="1h",
                close=100.0,
                ema_fast=110.0,
                ema_slow=100.0,
                rsi=30.0,
                macd=2.0,
                macd_signal=1.0,
                macd_histogram=1.0,
            ),
        ),
    ],
)
def test_assessment_threshold_boundaries(raw_score: int, expected_assessment: Assessment, snapshot: IndicatorSnapshot) -> None:
    result = StrategyService().evaluate_snapshot(snapshot)
    assert result.score == raw_score
    assert result.assessment == expected_assessment


def test_insufficient_data_behavior() -> None:
    service = StrategyService()
    missing_ema = service.evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=None,
            ema_slow=100.0,
            rsi=50.0,
            macd=1.0,
            macd_signal=1.0,
            macd_histogram=0.0,
        )
    )
    missing_rsi = service.evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=100.0,
            ema_slow=100.0,
            rsi=None,
            macd=1.0,
            macd_signal=1.0,
            macd_histogram=0.0,
        )
    )
    missing_macd = service.evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=100.0,
            ema_slow=100.0,
            rsi=50.0,
            macd=None,
            macd_signal=1.0,
            macd_histogram=0.0,
        )
    )
    missing_signal = service.evaluate_snapshot(
        IndicatorSnapshot(
            timestamp=datetime(2024, 1, 1, 3, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            close=100.0,
            ema_fast=100.0,
            ema_slow=100.0,
            rsi=50.0,
            macd=1.0,
            macd_signal=None,
            macd_histogram=0.0,
        )
    )

    assert missing_ema.assessment == Assessment.INSUFFICIENT_DATA
    assert missing_rsi.assessment == Assessment.INSUFFICIENT_DATA
    assert missing_macd.assessment == Assessment.INSUFFICIENT_DATA
    assert missing_signal.assessment == Assessment.INSUFFICIENT_DATA
    assert missing_ema.data_ready is False


def test_strategy_service_alignment_and_lookahead_protection() -> None:
    first = IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=110.0,
        ema_slow=100.0,
        rsi=80.0,
        macd=2.0,
        macd_signal=1.0,
        macd_histogram=1.0,
    )
    second = IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=90.0,
        ema_slow=100.0,
        rsi=20.0,
        macd=0.0,
        macd_signal=2.0,
        macd_histogram=-2.0,
    )
    snapshots = [first, second]
    results = StrategyService().build_results(snapshots)

    assert len(results) == 2
    assert results[0].timestamp == first.timestamp
    assert results[0].symbol == "BTCUSD"
    assert results[0].timeframe == "1h"
    assert results[0].score == 3

    future = list(snapshots)
    future[1] = IndicatorSnapshot(
        timestamp=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        close=100.0,
        ema_fast=200.0,
        ema_slow=100.0,
        rsi=10.0,
        macd=10.0,
        macd_signal=0.0,
        macd_histogram=10.0,
    )
    assert StrategyService().build_results([first])[0].score == 3

    with pytest.raises(ValueError):
        StrategyService().build_results([])


def test_strategy_api_endpoints() -> None:
    market = client.get("/market/candles", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 5})
    assert market.status_code == 200

    indicators = client.get("/indicators", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 5})
    assert indicators.status_code == 200

    strategy = client.get("/strategy", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 5})
    assert strategy.status_code == 200
    payload = strategy.json()
    assert len(payload) == 5
    assert payload[0]["symbol"] == "BTCUSD"
    assert payload[0]["timeframe"] == "1h"

    invalid_timeframe = client.get("/strategy", params={"symbol": "BTCUSD", "timeframe": "2h", "limit": 5})
    assert invalid_timeframe.status_code == 422

    invalid_limit = client.get("/strategy", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 1000})
    assert invalid_limit.status_code == 422


def test_existing_routes_still_work() -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    market = client.get("/market/candles", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 2})
    assert market.status_code == 200

    indicators = client.get("/indicators", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 2})
    assert indicators.status_code == 200
