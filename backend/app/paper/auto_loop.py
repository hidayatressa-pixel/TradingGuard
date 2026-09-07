from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.indicators.service import IndicatorService
from backend.app.market.models import Candle
from backend.app.paper.models import PaperAccount
from backend.app.paper.orchestration import AutoPaperEntryOrchestrator, AutoPaperEntryResult
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskPolicy
from backend.app.strategy.models import StrategyResult
from backend.app.strategy.service import StrategyService


class AutoPaperCycleResult(BaseModel):
    model_config = ConfigDict(strict=True)
    strategy: StrategyResult
    entry: AutoPaperEntryResult | None
    authorization: AutoPaperEntryResult | None = None
    account: PaperAccount
    reason: str
    mark_price: float | None = None
    unrealized_pnl: float | None = None
    unrealized_return_pct: float | None = None


class AutoPaperLoopService:
    """One authoritative PAPER cycle. Decisions use completed candles only."""
    def __init__(self, paper_service: PaperTradingService) -> None:
        self.paper_service = paper_service
        self.indicators = IndicatorService()
        self.strategy = StrategyService()
        self.orchestrator = AutoPaperEntryOrchestrator(paper_service)
        self.last_authorization: AutoPaperEntryResult | None = None

    def clear_authorization(self) -> None:
        self.last_authorization = None

    @staticmethod
    def _operational_instrument(account: PaperAccount) -> tuple[str, str] | None:
        if account.open_position is not None:
            return account.open_position.symbol, account.open_position.timeframe
        if account.pending_entry is not None:
            return account.pending_entry.symbol, account.pending_entry.timeframe
        if account.pending_exit is not None:
            return account.pending_exit.symbol, account.pending_exit.timeframe
        return None

    @staticmethod
    def _mark_to_market(account: PaperAccount, market_candle: Candle) -> tuple[float | None, float | None, float | None]:
        position = account.open_position
        if position is None or (position.symbol, position.timeframe) != (market_candle.symbol, market_candle.timeframe):
            return None, None, None
        mark = float(market_candle.close)
        gross = (mark - position.entry_price) * position.quantity
        estimated_exit_fee = mark * position.quantity * (account.config.transaction_cost_pct / 100.0)
        net = gross - position.entry_transaction_cost - estimated_exit_fee
        committed = position.entry_notional + position.entry_transaction_cost
        return mark, net, (net / committed) * 100.0 if committed > 0 else None

    def _result(self, *, strategy: StrategyResult, entry: AutoPaperEntryResult | None,
                account: PaperAccount, reason: str, market_candle: Candle) -> AutoPaperCycleResult:
        mark, pnl, return_pct = self._mark_to_market(account, market_candle)
        return AutoPaperCycleResult(
            strategy=strategy, entry=entry, authorization=self.last_authorization,
            account=account, reason=reason, mark_price=mark,
            unrealized_pnl=pnl, unrealized_return_pct=return_pct,
        )

    def _duplicate_reason(self, account: PaperAccount) -> str:
        if account.pending_exit is not None:
            return "EXIT signal is armed; waiting only for the next authoritative candle event to execute the PAPER exit."
        if account.open_position is not None:
            return "PAPER position remains active; this completed candle was already monitored. Waiting for the next completed candle for stop/exit monitoring."
        if account.pending_entry is not None:
            return "Sized PAPER BUY remains pending; this completed candle was already processed. Waiting for the next completed candle for execution revalidation."
        return "No new completed candle is available; the latest authoritative candle was already processed."

    def cycle(self, candles: list[Candle], *, risk_budget_pct: float = 0.5,
              max_allocation_pct: float | None = 20.0,
              policy: RiskPolicy | None = None) -> AutoPaperCycleResult:
        if len(candles) < 2:
            raise ValueError("Auto Paper cycle requires at least one completed candle plus the current market candle.")

        completed = candles[:-1]
        market_candle = candles[-1]
        results = self.strategy.build_results(self.indicators.build_snapshots(completed))
        if not results:
            raise ValueError("Strategy could not be derived from completed authoritative candle data.")
        current = results[-1]
        candle = completed[-1]
        account = self.paper_service.state()
        if not account.active or not account.config.paper_trading_enabled:
            self.clear_authorization()
            raise ValueError("Paper trading is inactive; autonomous cycle remains fail-closed.")
        if account.event_index == 0 and account.open_position is None and account.pending_action is None:
            self.clear_authorization()

        operational = self._operational_instrument(account)
        if operational is not None and (candle.symbol, candle.timeframe) != operational:
            expected_symbol, expected_timeframe = operational
            raise ValueError(
                f"Active PAPER workflow is locked to {expected_symbol}/{expected_timeframe}; "
                f"received {candle.symbol}/{candle.timeframe}."
            )

        self.paper_service.prepare_risk_day(candle.timestamp)
        account = self.paper_service.state()

        if account.last_event_timestamp is not None and candle.timestamp <= account.last_event_timestamp:
            return self._result(strategy=current, entry=None, account=account,
                                reason=self._duplicate_reason(account), market_candle=market_candle)

        entry = None
        flat = account.open_position is None and account.pending_entry is None and account.pending_exit is None
        # Deterministic opportunity gate: score <= 1 does not propose a BUY.
        # A score > 1 must immediately reach Auto Stop -> sizing -> Risk Guard;
        # Risk Guard remains the authority that can ALLOW/WARNING/BLOCK execution.
        eligible = current.data_ready and current.score > 1
        if flat and eligible:
            entry = self.orchestrator.evaluate_and_schedule_auto(
                strategy=current, candles=completed, risk_budget_pct=risk_budget_pct,
                max_allocation_pct=max_allocation_pct, policy=policy,
            )
            self.last_authorization = entry

        self.paper_service.process_auto_candle(candle, current, execution_policy=policy)
        account = self.paper_service.state()

        if entry is not None:
            return self._result(strategy=current, entry=entry, account=account,
                                reason=entry.reason, market_candle=market_candle)
        if account.pending_exit is not None:
            reason = f"EXIT ARMED: completed strategy score={current.score} ({current.assessment.value}); PAPER exit is scheduled for the next authoritative candle event."
        elif account.open_position is not None:
            reason = f"POSITION MONITORING: completed strategy score={current.score} ({current.assessment.value}); Stop Loss and exit rules remain active."
        elif account.pending_entry is not None:
            reason = "Sized PAPER BUY is pending next-completed-candle execution revalidation."
        elif eligible:
            reason = f"Score {current.score} passed the opportunity gate (>1), but no entry is authorized in the current account state."
        elif not current.data_ready:
            reason = "WAIT: completed candle does not yet have enough indicator data for an authoritative score."
        elif current.score < 0:
            reason = f"BLOCK BUY: completed strategy score={current.score} is below 0."
        else:
            reason = f"WAIT: completed strategy score={current.score} is inside the 0..1 no-entry zone."
        return self._result(strategy=current, entry=None, account=account,
                            reason=reason, market_candle=market_candle)
