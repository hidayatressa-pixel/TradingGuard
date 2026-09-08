from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.app.paper.models import PaperAccount


class PaperAccountRepository:
    """Small SQLite state store for PAPER validation; no broker credentials are stored."""

    def __init__(self, path: str = "data/tradingguard.db") -> None:
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()

    def _connect(self)->sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init(self)->None:
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS paper_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    def load(self)->PaperAccount|None:
        with self._connect() as db:
            row=db.execute("SELECT payload FROM paper_state WHERE id=1").fetchone()
        return PaperAccount.model_validate_json(row[0]) if row else None

    def save(self,account:PaperAccount)->None:
        payload=account.model_dump_json()
        with self._connect() as db:
            db.execute("INSERT INTO paper_state(id,payload,updated_at) VALUES(1,?,CURRENT_TIMESTAMP) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=CURRENT_TIMESTAMP",(payload,))
