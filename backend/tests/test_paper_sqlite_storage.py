from backend.app.paper.models import PaperAccount, PaperTradingConfig
from backend.app.paper.storage import PaperSQLiteStore


def account() -> PaperAccount:
    config = PaperTradingConfig()
    return PaperAccount(
        config=config, active=True, initial_capital=10000.0, cash=10000.0,
        realized_equity=10000.0, peak_realized_equity=10000.0,
        day_start_equity=10000.0,
    )


def test_sqlite_round_trip_account(tmp_path):
    store = PaperSQLiteStore(tmp_path / "tradingguard.sqlite3")
    original = account()
    original.cash = 8765.43
    store.save_account(original)
    restored = store.load_account()
    assert restored is not None
    assert restored.cash == 8765.43
    assert restored.active is True


def test_decision_journal_is_durable(tmp_path):
    path = tmp_path / "tradingguard.sqlite3"
    store = PaperSQLiteStore(path)
    store.record_decision(
        action="BUY", symbol="BTCUSDT", timeframe="1m",
        strategy_assessment="STRONG_BEARISH", strategy_score=-4,
        decision="BLOCK", executed=False,
        reason="Market condition rejected manual BUY.",
    )
    reopened = PaperSQLiteStore(path)
    rows = reopened.list_decisions()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTCUSDT"
    assert rows[0]["decision"] == "BLOCK"
    assert rows[0]["executed"] == 0
