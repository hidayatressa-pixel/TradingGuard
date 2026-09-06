from __future__ import annotations

from datetime import datetime

from backend.app.market.models import Candle
from backend.app.risk.execution import ExecutionRiskRevalidationService
from backend.app.risk.models import RiskDecision, RiskPolicy, RiskResult
from backend.app.strategy.models import Assessment, StrategyResult
from .models import PaperAccount, PaperExitReason, PaperPosition, PaperTrade, PaperTradingConfig, PendingEntry, PendingExit


class PaperTradingService:
    """Runs deterministic, long-only paper execution in one in-memory account."""
    def __init__(self)->None:
        self.account:PaperAccount|None=None
        self.execution_revalidation=ExecutionRiskRevalidationService()

    def _new_account(self,config:PaperTradingConfig,active:bool)->PaperAccount:
        return PaperAccount(config=config,active=active,initial_capital=config.initial_capital,cash=config.initial_capital,realized_equity=config.initial_capital,peak_realized_equity=config.initial_capital,day_start_equity=config.initial_capital)

    def start(self,config:PaperTradingConfig|None=None)->PaperAccount:
        if self.account is not None and self.account.active: raise ValueError("Paper trading session is already active; reset it before starting again.")
        active_config=config or (self.account.config if self.account is not None else PaperTradingConfig()); self.account=self._new_account(active_config,True); return self.account

    def reset(self)->PaperAccount:
        config=self.account.config if self.account is not None else PaperTradingConfig(); self.account=self._new_account(config,False); return self.account

    def state(self)->PaperAccount:
        if self.account is None: raise ValueError("Paper trading session has not been started.")
        return self.account

    def _roll_risk_day(self,timestamp:datetime)->None:
        account=self.state(); day=timestamp.date().isoformat()
        if account.risk_day != day: account.risk_day=day; account.day_start_equity=account.realized_equity

    def _validate_event(self,candle:Candle,strategy:StrategyResult,risk:RiskResult)->None:
        if candle.timestamp!=strategy.timestamp or candle.timestamp!=risk.timestamp: raise ValueError("Candle, strategy, and risk timestamps must match.")
        if candle.symbol!=strategy.symbol or candle.symbol!=risk.symbol: raise ValueError("Candle, strategy, and risk symbols must match.")
        if candle.timeframe!=strategy.timeframe or candle.timeframe!=risk.timeframe: raise ValueError("Candle, strategy, and risk timeframes must match.")
        if self.account is not None and self.account.last_event_timestamp is not None and candle.timestamp<=self.account.last_event_timestamp: raise ValueError("Paper events must arrive in strictly increasing chronological order.")

    def _execute_entry(self,candle:Candle,pending:PendingEntry)->None:
        account=self.state()
        if not account.config.paper_trading_enabled: account.pending_entry=None; return
        if account.open_position is not None or account.pending_exit is not None: account.pending_entry=None; return
        effective_price=float(candle.open)*(1.0+account.config.slippage_pct/100.0)
        if pending.stop_loss_price is not None and pending.stop_loss_price>=effective_price: raise ValueError("Paper stop-loss must remain below the effective long entry price.")
        fee_rate=account.config.transaction_cost_pct/100.0
        if pending.quantity is None:
            target_allocation=account.realized_equity*(account.config.position_size_pct/100.0); quantity=target_allocation/(effective_price*(1.0+fee_rate))
        else: quantity=pending.quantity
        entry_notional=quantity*effective_price; entry_fee=entry_notional*fee_rate; total_outflow=entry_notional+entry_fee
        if quantity<=0 or total_outflow>account.cash+1e-9: raise ValueError("Paper entry would exceed available cash; authoritative quantity will not be silently resized.")
        cash_before=account.cash; account.cash=max(account.cash-total_outflow,0.0); account.open_position=PaperPosition(symbol=pending.symbol,timeframe=pending.timeframe,entry_signal_timestamp=pending.signal_timestamp,entry_timestamp=candle.timestamp,entry_price=effective_price,quantity=quantity,entry_notional=entry_notional,entry_transaction_cost=entry_fee,entry_assessment=pending.assessment,cash_before_entry=cash_before,cash_after_entry=account.cash,stop_loss_price=pending.stop_loss_price); account.total_transaction_cost+=entry_fee; account.pending_entry=None

    def schedule_sized_entry(self,*,strategy:StrategyResult,risk:RiskResult,quantity:float,stop_loss_price:float,expected_equity:float)->PaperAccount:
        account=self.state()
        if not account.active or not account.config.paper_trading_enabled: raise ValueError("Paper trading is not enabled; sized entry remains fail-closed.")
        if account.open_position is not None or account.pending_entry is not None or account.pending_exit is not None: raise ValueError("Paper account is not flat; sized entry remains fail-closed.")
        if risk.decision!=RiskDecision.ALLOW: raise ValueError("Risk Guard ALLOW is required for a sized paper entry.")
        if not strategy.data_ready or strategy.assessment not in {Assessment.BULLISH,Assessment.STRONG_BULLISH}: raise ValueError("Eligible bullish strategy data is required for a sized paper entry.")
        if abs(expected_equity-account.realized_equity)>max(1e-9,abs(account.realized_equity)*1e-9): raise ValueError("Risk sizing equity is stale or does not match authoritative paper equity.")
        account.pending_entry=PendingEntry(signal_timestamp=strategy.timestamp,symbol=strategy.symbol,timeframe=strategy.timeframe,assessment=strategy.assessment.value,execute_index=account.event_index+1,stop_loss_price=stop_loss_price,quantity=quantity); return account

    def _execute_due_sized_entry(self,candle:Candle,strategy:StrategyResult,pending:PendingEntry,policy:RiskPolicy|None)->bool:
        account=self.state()
        result=self.execution_revalidation.evaluate(account=account,candle=candle,strategy=strategy,pending=pending,policy=policy)
        if not result.allowed:
            account.pending_entry=None
            return False
        self._execute_entry(candle,pending)
        return True

    def _close_position(self,*,timestamp:datetime,effective_price:float,exit_signal_timestamp:datetime,exit_assessment:str,exit_reason:PaperExitReason)->None:
        account=self.state(); position=account.open_position
        if position is None: return
        exit_notional=position.quantity*effective_price; exit_fee=exit_notional*(account.config.transaction_cost_pct/100.0); gross_pnl=(effective_price-position.entry_price)*position.quantity; total_fee=position.entry_transaction_cost+exit_fee; net_pnl=gross_pnl-total_fee; equity_before=account.realized_equity; account.cash+=exit_notional-exit_fee; account.realized_equity=account.cash; committed_capital=position.entry_notional+position.entry_transaction_cost
        if committed_capital<=0: raise ValueError("Committed capital must be positive.")
        account.closed_trades.append(PaperTrade(symbol=position.symbol,timeframe=position.timeframe,entry_signal_timestamp=position.entry_signal_timestamp,entry_timestamp=position.entry_timestamp,entry_price=position.entry_price,exit_signal_timestamp=exit_signal_timestamp,exit_timestamp=timestamp,exit_price=effective_price,quantity=position.quantity,entry_notional=position.entry_notional,exit_notional=exit_notional,gross_pnl=gross_pnl,entry_transaction_cost=position.entry_transaction_cost,exit_transaction_cost=exit_fee,transaction_cost=total_fee,net_pnl=net_pnl,return_pct=(net_pnl/committed_capital)*100.0,equity_before=equity_before,equity_after=account.realized_equity,entry_assessment=position.entry_assessment,exit_assessment=exit_assessment,exit_reason=exit_reason)); account.total_transaction_cost+=exit_fee; account.open_position=None; account.pending_exit=None; account.peak_realized_equity=max(account.peak_realized_equity,account.realized_equity)

    def _execute_exit(self,candle:Candle,pending:PendingExit)->None:
        if self.state().open_position is None: self.state().pending_exit=None; return
        effective_price=float(candle.open)*(1.0-self.state().config.slippage_pct/100.0); self._close_position(timestamp=candle.timestamp,effective_price=effective_price,exit_signal_timestamp=pending.signal_timestamp,exit_assessment=pending.assessment,exit_reason=PaperExitReason.STRATEGY)

    def _execute_stop_if_triggered(self,candle:Candle)->bool:
        account=self.state(); position=account.open_position
        if position is None or position.stop_loss_price is None: return False
        stop=position.stop_loss_price
        if float(candle.open)<=stop: base_fill=float(candle.open)
        elif float(candle.low)<=stop: base_fill=stop
        else: return False
        effective_price=base_fill*(1.0-account.config.slippage_pct/100.0); self._close_position(timestamp=candle.timestamp,effective_price=effective_price,exit_signal_timestamp=candle.timestamp,exit_assessment="STOP_LOSS",exit_reason=PaperExitReason.STOP_LOSS); return True

    def process_candle(self,candle:Candle,strategy:StrategyResult,risk:RiskResult,stop_loss_price:float|None=None,execution_policy:RiskPolicy|None=None)->PaperAccount:
        account=self.state(); self._validate_event(candle,strategy,risk); self._roll_risk_day(candle.timestamp); current_index=account.event_index; position_at_candle_start=account.open_position is not None
        if not account.config.paper_trading_enabled: account.pending_entry=None
        if account.pending_entry is not None and account.pending_entry.execute_index==current_index:
            if account.pending_entry.quantity is not None:
                self._execute_due_sized_entry(candle,strategy,account.pending_entry,execution_policy)
            else:
                self._execute_entry(candle,account.pending_entry)
        if account.pending_exit is not None and account.pending_exit.execute_index==current_index: self._execute_exit(candle,account.pending_exit)
        stopped=False
        if position_at_candle_start and account.open_position is not None: stopped=self._execute_stop_if_triggered(candle)
        if not stopped:
            # V0.7 legacy scheduling is retained for compatibility. Operational V0.9 auto-BUY must use schedule_sized_entry,
            # whose quantity-bearing pending entry is the only path that receives fresh next-open Risk Guard revalidation.
            if account.config.paper_trading_enabled and account.open_position is None and account.pending_entry is None:
                if strategy.data_ready and strategy.assessment in {Assessment.BULLISH,Assessment.STRONG_BULLISH} and risk.decision==RiskDecision.ALLOW: account.pending_entry=PendingEntry(signal_timestamp=strategy.timestamp,symbol=strategy.symbol,timeframe=strategy.timeframe,assessment=strategy.assessment.value,execute_index=current_index+1,stop_loss_price=stop_loss_price)
            elif account.open_position is not None and account.pending_exit is None:
                if strategy.data_ready and strategy.assessment in {Assessment.NEUTRAL,Assessment.BEARISH,Assessment.STRONG_BEARISH}: account.pending_exit=PendingExit(signal_timestamp=strategy.timestamp,symbol=strategy.symbol,timeframe=strategy.timeframe,assessment=strategy.assessment.value,execute_index=current_index+1)
        account.last_event_timestamp=candle.timestamp; account.event_index+=1; return account

    def performance(self): return self.state().performance()
