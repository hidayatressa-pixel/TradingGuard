from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.indicators.calculator import (
    MACDResult,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
)
from backend.app.indicators.service import IndicatorService
from backend.app.main import app
from backend.app.market.data_provider import MockMarketDataProvider
from backend.app.market.models import Candle

client = TestClient(app)


def test_ema_known_values() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    expected = [None, None, 2.0, 3.0, 4.0]
    assert calculate_ema(values, 3) == expected


def test_ema_warmup_alignment_and_period_validation() -> None:
    assert calculate_ema([10.0, 20.0], 3) == [None, None]
    with pytest.raises(ValueError):
        calculate_ema([1.0, 2.0], 0)


def test_ema_rejects_nan_or_infinity() -> None:
    with pytest.raises(ValueError):
        calculate_ema([1.0, math.nan, 3.0], 2)
    with pytest.raises(ValueError):
        calculate_ema([1.0, float("inf"), 3.0], 2)


def test_rsi_known_reference_values() -> None:
    rising = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert calculate_rsi(rising, 3) == [None, None, None, 100.0, 100.0]

    falling = [5.0, 4.0, 3.0, 2.0, 1.0]
    assert calculate_rsi(falling, 3) == [None, None, None, 0.0, 0.0]


def test_rsi_flat_prices_use_neutral_value() -> None:
    flat = [10.0, 10.0, 10.0, 10.0, 10.0]
    result = calculate_rsi(flat, 3)
    assert result[0] is None
    assert result[1] is None
    assert result[2] is None
    assert result[3] == 50.0


def test_rsi_insufficient_data_returns_all_none() -> None:
    assert calculate_rsi([1.0, 2.0, 3.0], 3) == [None, None, None]
    assert calculate_rsi([1.0, 2.0, 3.0, 4.0], 3) == [None, None, None, 100.0]


def test_rsi_stays_within_bounds_and_rejects_invalid_values() -> None:
    values = [10.0, 11.0, 12.0, 11.0, 13.0, 12.0, 14.0, 15.0, 14.0]
    result = calculate_rsi(values, 3)
    assert all(value is None or 0.0 <= value <= 100.0 for value in result)

    with pytest.raises(ValueError):
        calculate_rsi([1.0, -2.0, 3.0], 2)
    with pytest.raises(ValueError):
        calculate_rsi([1.0, math.nan, 3.0], 2)


def test_rsi_mixed_gain_loss_known_value() -> None:
    values = [100.0, 101.0, 99.0, 102.0, 100.0]
    result = calculate_rsi(values, 3)
    assert result[3] is not None
    assert 0.0 <= result[3] <= 100.0
    assert result[4] is not None
    assert 0.0 <= result[4] <= 100.0


def test_macd_alignment_and_histogram() -> None:
    values = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0]
    macd = calculate_macd(values, 3, 5, 2)

    assert isinstance(macd, MACDResult)
    assert len(macd.macd) == len(values)
    assert len(macd.signal) == len(values)
    assert len(macd.histogram) == len(values)
    for idx in range(len(values)):
        if macd.macd[idx] is not None and macd.signal[idx] is not None:
            assert macd.histogram[idx] == macd.macd[idx] - macd.signal[idx]


def test_macd_rejects_invalid_periods() -> None:
    with pytest.raises(ValueError):
        calculate_macd([1.0, 2.0, 3.0], fast_period=3, slow_period=3)
    with pytest.raises(ValueError):
        calculate_macd([1.0, 2.0, 3.0], fast_period=0, slow_period=2)


def test_indicator_service_builds_snapshots_and_preserves_input() -> None:
    candles = [
        Candle(
            timestamp=datetime(2024, 1, 1, 0, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            open=100.0,
            high=101.0,
            low=99.5,
            close=100.5,
            volume=120.0,
        ),
        Candle(
            timestamp=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            open=100.5,
            high=102.0,
            low=100.0,
            close=101.5,
            volume=130.0,
        ),
        Candle(
            timestamp=datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            open=101.5,
            high=102.5,
            low=101.0,
            close=102.0,
            volume=140.0,
        ),
    ]
    snapshots = IndicatorService().build_snapshots(candles)
    assert len(snapshots) == len(candles)
    assert snapshots[0].timestamp == candles[0].timestamp
    assert snapshots[0].symbol == "BTCUSD"
    assert snapshots[0].timeframe == "1h"
    assert candles[0].close == 100.5
    assert candles[0].timestamp == datetime(2024, 1, 1, 0, tzinfo=timezone.utc)


def test_indicator_service_rejects_invalid_dataset() -> None:
    with pytest.raises(ValueError):
        IndicatorService().build_snapshots([])

    ts = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
    candles = [
        Candle(
            timestamp=ts,
            symbol="BTCUSD",
            timeframe="1h",
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=100.0,
        ),
        Candle(
            timestamp=ts,
            symbol="BTCUSD",
            timeframe="1h",
            open=101.0,
            high=102.0,
            low=100.0,
            close=101.5,
            volume=100.0,
        ),
    ]
    with pytest.raises(ValueError):
        IndicatorService().build_snapshots(candles)


def test_indicators_endpoint_returns_data() -> None:
    response = client.get("/indicators", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 5
    assert payload[0]["symbol"] == "BTCUSD"
    assert payload[0]["timeframe"] == "1h"


def test_indicators_invalid_timeframe_and_limit_are_rejected() -> None:
    bad_timeframe = client.get("/indicators", params={"symbol": "BTCUSD", "timeframe": "2h", "limit": 5})
    assert bad_timeframe.status_code == 422

    bad_limit = client.get("/indicators", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 1000})
    assert bad_limit.status_code == 422


def test_existing_market_and_health_endpoints_still_work() -> None:
    market = client.get("/market/candles", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 3})
    assert market.status_code == 200

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
