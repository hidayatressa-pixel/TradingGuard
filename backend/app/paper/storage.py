from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import PaperAccount


class PaperSQLiteStore:
    """Small durable store for the single-user PAPER account and experiment decisions."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("TRADINGGUARD_DB_PATH", "data/tradingguard.sqlite3")
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS paper_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    account_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS decision_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    strategy_assessment TEXT NOT NULL,
                    strategy_score INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    executed INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    execution_price REAL,
                    risk_decision TEXT,
                    stop_loss_price REAL,
                    risk_per_trade_pct REAL,
                    quantity REAL,
                    mode TEXT NOT NULL
                )"""
            )

    def load_account(self) -> PaperAccount | None:
        with self._connect() as connection:
            row = connection.execute("SELECT account_json FROM paper_state WHERE id = 1").fetchone()
        return None if row is None else PaperAccount.model_validate_json(row[0])

    def save_account(self, account: PaperAccount) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = account.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO paper_state(id, account_json, updated_at) VALUES(1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET account_json=excluded.account_json, updated_at=excluded.updated_at""",
                (payload, now),
            )

    def record_decision(self, *, action: str, symbol: str, timeframe: str,
                        strategy_assessment: str, strategy_score: int, decision: str,
                        executed: bool, reason: str, execution_price: float | None = None,
                        risk_decision: str | None = None, stop_loss_price: float | None = None,
                        risk_per_trade_pct: float | None = None, quantity: float | None = None,
                        mode: str = "MANUAL_GUARDED") -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO decision_journal(
                    created_at,action,symbol,timeframe,strategy_assessment,strategy_score,
                    decision,executed,reason,execution_price,risk_decision,stop_loss_price,
                    risk_per_trade_pct,quantity,mode
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (datetime.now(timezone.utc).isoformat(), action, symbol, timeframe,
                 strategy_assessment, strategy_score, decision, int(executed), reason,
                 execution_price, risk_decision, stop_loss_price, risk_per_trade_pct,
                 quantity, mode),
            )

    def list_decisions(self, limit: int = 200) -> list[dict[str, object]]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM decision_journal ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
