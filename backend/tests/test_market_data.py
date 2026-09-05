from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.market.data_provider import MockMarketDataProvider
from backend.app.market.models import Candle
from backend.app.market.validation import validate_candle_dataset

client = TestClient(app)


def test_valid_candle_model() -> None:
    candle = Candle(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        open=100.0,
        high=101.5,
        low=99.5,
        close=101.0,
        volume=1250.0,
    )

    assert candle.symbol == "BTCUSD"
    assert candle.high >= candle.close >= candle.low


def test_invalid_ohlc_candle_rejection() -> None:
    with pytest.raises(ValidationError):
        Candle(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            open=100.0,
            high=90.0,
            low=95.0,
            close=101.0,
            volume=100.0,
        )


def test_high_less_than_close_is_invalid() -> None:
    with pytest.raises(ValidationError):
        Candle(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            open=100.0,
            high=99.0,
            low=95.0,
            close=101.0,
            volume=100.0,
        )


def test_low_greater_than_close_is_invalid() -> None:
    with pytest.raises(ValidationError):
        Candle(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            open=100.0,
            high=105.0,
            low=102.0,
            close=101.0,
            volume=100.0,
        )


def test_high_less_than_low_is_invalid() -> None:
    with pytest.raises(ValidationError):
        Candle(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            open=100.0,
            high=95.0,
            low=96.0,
            close=101.0,
            volume=100.0,
        )


def test_equal_boundary_values_are_valid() -> None:
    candle = Candle(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        open=100.0,
        high=100.0,
        low=100.0,
        close=100.0,
        volume=100.0,
    )
    assert candle.high == candle.open == candle.close == candle.low

    candle_with_equal_extremes = Candle(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BTCUSD",
        timeframe="1h",
        open=100.0,
        high=105.0,
        low=100.0,
        close=105.0,
        volume=100.0,
    )
    assert candle_with_equal_extremes.high == candle_with_equal_extremes.close
    assert candle_with_equal_extremes.low == candle_with_equal_extremes.open


def test_negative_volume_rejection() -> None:
    with pytest.raises(ValidationError):
        Candle(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=-1.0,
        )


def test_mock_provider_is_deterministic() -> None:
    provider = MockMarketDataProvider(symbol="BTCUSD", timeframe="1h", candle_count=12)

    first = provider.get_candles(symbol="BTCUSD", timeframe="1h", limit=12)
    second = provider.get_candles(symbol="BTCUSD", timeframe="1h", limit=12)

    assert first == second
    assert len(first) == 12
    assert first[0].symbol == "BTCUSD"
    assert first[0].timeframe == "1h"


def test_candle_order_validation_returns_chronological_errors() -> None:
    candles = [
        Candle(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=100.0,
        ),
        Candle(
            timestamp=datetime(2023, 12, 31, tzinfo=timezone.utc),
            symbol="BTCUSD",
            timeframe="1h",
            open=101.0,
            high=102.0,
            low=100.0,
            close=101.5,
            volume=100.0,
        ),
    ]

    errors = validate_candle_dataset(candles)
    assert any("chronological" in error.lower() for error in errors)


def test_duplicate_timestamp_detection() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
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
            open=100.5,
            high=101.5,
            low=99.5,
            close=101.0,
            volume=110.0,
        ),
    ]

    errors = validate_candle_dataset(candles)
    assert any("duplicate" in error.lower() for error in errors)


def test_empty_dataset_handling() -> None:
    assert validate_candle_dataset([]) == ["Dataset is empty."]


def test_market_candles_endpoint_returns_data() -> None:
    response = client.get("/market/candles", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 5
    assert payload[0]["symbol"] == "BTCUSD"
    assert payload[0]["timeframe"] == "1h"


def test_invalid_limit_is_rejected() -> None:
    response = client.get("/market/candles", params={"symbol": "BTCUSD", "timeframe": "1h", "limit": 1000})

    assert response.status_code == 422


def test_health_endpoint_still_works() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
