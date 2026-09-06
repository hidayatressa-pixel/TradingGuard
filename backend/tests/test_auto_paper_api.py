from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.main import app, paper_service

client = TestClient(app)
TS = datetime(2026, 9, 6, tzinfo=timezone.utc).isoformat()


def bullish_strategy() -> dict:
    return {
        "timestamp": TS,
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "score": 4,
        "normalized_score": 90,
        "assessment": "BULLISH",
        "data_ready": True,
        "evidence": [],
    }


def setup_function() -> None:
    paper_service.reset()


def start_paper() -> None:
    response = client.post("/paper/start", json={"config": {"transaction_cost_pct": 0.0, "slippage_pct": 0.0}})
    assert response.status_code == 200
    paper_service.state().risk_day = "2026-09-06"


def test_auto_entry_api_schedules_authoritative_sized_pending_buy() -> None:
    start_paper()
    response = client.post("/paper/auto-entry", json={
        "strategy": bullish_strategy(),
        "reference_entry_price": 100.0,
        "stop_loss_price": 95.0,
        "risk_budget_pct": 0.5,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["scheduled"] is True
    assert body["execution_permission_established"] is True
    assert body["gate"]["risk"]["decision"] == "ALLOW"
    assert body["gate"]["sizing"]["final_quantity"] == 10.0
    assert paper_service.state().pending_entry is not None
    assert paper_service.state().pending_entry.quantity == 10.0
    assert paper_service.state().pending_entry.stop_loss_price == 95.0


def test_auto_entry_api_warning_does_not_schedule() -> None:
    start_paper()
    response = client.post("/paper/auto-entry", json={
        "strategy": bullish_strategy(),
        "reference_entry_price": 100.0,
        "stop_loss_price": 95.0,
        "risk_budget_pct": 0.8,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["scheduled"] is False
    assert body["gate"]["risk"]["decision"] == "WARNING"
    assert paper_service.state().pending_entry is None


def test_auto_entry_api_rejects_invalid_long_stop() -> None:
    start_paper()
    response = client.post("/paper/auto-entry", json={
        "strategy": bullish_strategy(),
        "reference_entry_price": 100.0,
        "stop_loss_price": 101.0,
        "risk_budget_pct": 0.5,
    })
    assert response.status_code == 422
    assert paper_service.state().pending_entry is None


def test_auto_entry_api_fails_closed_when_paper_inactive() -> None:
    response = client.post("/paper/auto-entry", json={
        "strategy": bullish_strategy(),
        "reference_entry_price": 100.0,
        "stop_loss_price": 95.0,
        "risk_budget_pct": 0.5,
    })
    assert response.status_code == 200
    assert response.json()["scheduled"] is False
    assert paper_service.state().pending_entry is None
