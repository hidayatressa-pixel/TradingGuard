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
    authorization: AutoPaperEntryResult | None = None
    account: PaperAccount
    reason: str


class AutoPaperLoopService:
    """One authoritative PAPER cycle. Decisions use completed candles only."""
    def __init__(self, paper_service: PaperTradingService) -> None:
        self.paper_service = paper_service
        self.indicators = IndicatorService()
        self.strategy = StrategyService()
        self.orchestrator = AutoPaperEntryOrchestrator(paper_service)
        # Audit snapshot of the latest explicit entry-gate result. It is presentation/audit
        # state only: execution still depends exclusively on PaperTradingService interlocks.
        self.last_authorization: AutoPaperEntryResult | None = None

    def cycle(self, candles: list[Candle], *, risk_budget_pct: float = 0.5,
              max_allocation_pct: float | None = 20.0,
              policy: RiskPolicy | None = None) -> AutoPaperCycleResult:
        if len(candles) < 2:
            raise ValueError("Auto Paper cycle requires at least one completed candle plus the current market candle.")

        completed = candles[:-1]
        results = self.strategy.build_results(self.indicators.build_snapshots(completed))
        if not results:
            raise ValueError("Strategy could not be derived from completed authoritative candle data.")
        current = results[-1]
        candle = completed[-1]
        account = self.paper_service.state()
        if not account.active or not account.config.paper_trading_enabled:
            self.last_authorization = None
            raise ValueError("Paper trading is inactive; autonomous cycle remains fail-closed.")

        self.paper_service.prepare_risk_day(candle.timestamp)
        account = self.paper_service.state()

        if account.last_event_timestamp is not None and candle.timestamp <= account.last_event_timestamp:
            return AutoPaperCycleResult(strategy=current, entry=None, authorization=self.last_authorization,
                                        account=account,
                                        reason="Completed candle already processed; waiting for the next completed candle.")

        entry = None
        flat = account.open_position is None and account.pending_entry is None and account.pending_exit is None
        eligible = current.data_ready and current.assessment in {Assessment.BULLISH, Assessment.STRONG_BULLISH}
        if flat and eligible:
            # Every eligible flat setup must reach an explicit gate result. WAIT is never used as
            # a substitute for Risk Guard evaluation once authoritative bullish data is available.
            entry = self.orchestrator.evaluate_and_schedule_auto(
                strategy=current, candles=completed, risk_budget_pct=risk_budget_pct,
                max_allocation_pct=max_allocation_pct, policy=policy,
            )
            self.last_authorization = entry

        self.paper_service.process_auto_candle(candle, current, execution_policy=policy)
        account = self.paper_service.state()

        if entry is not None:
            return AutoPaperCycleResult(strategy=current, entry=entry, authorization=self.last_authorization,
                                        account=account, reason=entry.reason)
        if account.open_position is not None:
            reason = "PAPER position is active; entry authorization is preserved and stop/exit monitoring continues."
        elif account.pending_entry is not None:
            reason = "Sized PAPER BUY is pending next-completed-candle execution revalidation."
        elif eligible:
            reason = "Bullish setup was evaluated but no new entry is currently schedulable."
        else:
            reason = "Strategy interlock is not bullish; no new PAPER entry considered."
        return AutoPaperCycleResult(strategy=current, entry=None, authorization=self.last_authorization,
                                    account=account, reason=reason)
