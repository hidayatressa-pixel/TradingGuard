from __future__ import annotations

from datetime import datetime

from backend.app.market.models import Candle
from backend.app.risk.models import RiskPolicy, RiskResult
from backend.app.strategy.models import StrategyResult

from .models import PaperAccount, PaperTradingConfig
from .service import PaperTradingService
from .storage import PaperSQLiteStore


class PersistentPaperTradingService(PaperTradingService):
    """PaperTradingService with durable SQLite state after every public mutation."""

    def __init__(self, store: PaperSQLiteStore | None = None) -> None:
        super().__init__()
        self.store = store or PaperSQLiteStore()
        self.account = self.store.load_account()

    def _persist(self, account: PaperAccount) -> PaperAccount:
        self.store.save_account(account)
        return account

    def start(self, config: PaperTradingConfig | None = None) -> PaperAccount:
        return self._persist(super().start(config))

    def reset(self) -> PaperAccount:
        return self._persist(super().reset())

    def prepare_risk_day(self, timestamp: datetime) -> PaperAccount:
        return self._persist(super().prepare_risk_day(timestamp))

    def execute_manual_guarded_entry(self, **kwargs) -> PaperAccount:
        return self._persist(super().execute_manual_guarded_entry(**kwargs))

    def execute_manual_exit(self, **kwargs) -> PaperAccount:
        return self._persist(super().execute_manual_exit(**kwargs))

    def schedule_sized_entry(self, **kwargs) -> PaperAccount:
        return self._persist(super().schedule_sized_entry(**kwargs))

    def process_auto_candle(self, candle: Candle, strategy: StrategyResult,
                            execution_policy: RiskPolicy | None = None) -> PaperAccount:
        return self._persist(super().process_auto_candle(candle, strategy, execution_policy))

    def process_candle(self, candle: Candle, strategy: StrategyResult, risk: RiskResult,
                       stop_loss_price: float | None = None,
                       execution_policy: RiskPolicy | None = None) -> PaperAccount:
        return self._persist(super().process_candle(candle, strategy, risk, stop_loss_price, execution_policy))
