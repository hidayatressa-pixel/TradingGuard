from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.indicators.service import IndicatorService
from backend.app.market.models import Candle
from backend.app.paper.models import PaperAccount
from backend.app.paper.orchestration import AutoPaperEntryOrchestrator, AutoPaperEntryResult
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskPolicy
from backend.app.strategy.models import Assessment, StrategyResult
from backend.app.strategy.service import StrategyService


class AutoPaperCycleResult(BaseModel):
    model_config = ConfigDict(strict=True)
    strategy: StrategyResult
    entry: AutoPaperEntryResult | None
    account: PaperAccount
    reason: str


class AutoPaperLoopService:
    """One deterministic autonomous cycle. Scheduling/timing stays outside this service."""
    def __init__(self, paper_service: PaperTradingService) -> None:
        self.paper_service = paper_service
        self.indicators = IndicatorService()
        self.strategy = StrategyService()
        self.orchestrator = AutoPaperEntryOrchestrator(paper_service)

    def cycle(self, candles: list[Candle], *, risk_budget_pct: float = 0.5,
              max_allocation_pct: float | None = 20.0,
              policy: RiskPolicy | None = None) -> AutoPaperCycleResult:
        if not candles:
            raise ValueError("Auto Paper cycle requires authoritative candle data.")
        results = self.strategy.build_results(self.indicators.build_snapshots(candles))
        if not results:
            raise ValueError("Strategy could not be derived from authoritative candle data.")
        current = results[-1]
        account = self.paper_service.state()
        entry = None
        if account.open_position is None and account.pending_entry is None and account.pending_exit is None:
            if current.data_ready and current.assessment in {Assessment.BULLISH, Assessment.STRONG_BULLISH}:
                entry = self.orchestrator.evaluate_and_schedule_auto(strategy=current, candles=candles,
                    risk_budget_pct=risk_budget_pct, max_allocation_pct=max_allocation_pct, policy=policy)
                account = self.paper_service.state()
                return AutoPaperCycleResult(strategy=current, entry=entry, account=account, reason=entry.reason)
            return AutoPaperCycleResult(strategy=current, entry=None, account=account,
                                        reason="Strategy interlock is not bullish; no new PAPER entry considered.")
        return AutoPaperCycleResult(strategy=current, entry=None, account=account,
                                    reason="Paper account has an open or pending action; new entry interlock remains closed.")
