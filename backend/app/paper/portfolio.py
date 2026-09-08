from __future__ import annotations

from datetime import datetime

from backend.app.paper.models import PaperAccount, PaperExitReason, PaperPosition, PaperTrade
from backend.app.paper.service import PaperTradingService
from backend.app.risk.models import RiskDecision, RiskResult
from backend.app.strategy.models import Assessment, StrategyResult


class PaperPortfolioService:
    """Manual PAPER portfolio execution with one long position per symbol."""

    def __init__(self, paper_service: PaperTradingService) -> None:
        self.paper_service = paper_service

    def buy(self, *, strategy: StrategyResult, risk: RiskResult, quantity: float,
            stop_loss_price: float, execution_price: float, timestamp: datetime) -> PaperAccount:
        account=self.paper_service.state(); self.paper_service.prepare_risk_day(timestamp)
        if not account.active or not account.config.paper_trading_enabled: raise ValueError("Paper trading is inactive.")
        if account.position_for(strategy.symbol) is not None: raise ValueError(f"Paper position for {strategy.symbol} is already open.")
        if risk.decision!=RiskDecision.ALLOW: raise ValueError("Risk Guard ALLOW is required for manual BUY.")
        if not strategy.data_ready or strategy.assessment not in {Assessment.BULLISH,Assessment.STRONG_BULLISH}: raise ValueError("Manual BUY is rejected because current completed strategy is not bullish.")
        if quantity<=0 or execution_price<=0 or stop_loss_price<=0: raise ValueError("Manual execution inputs must be positive.")
        effective_price=float(execution_price)*(1.0+account.config.slippage_pct/100.0)
        if stop_loss_price>=effective_price: raise ValueError("Paper stop-loss must remain below the effective long entry price.")
        fee_rate=account.config.transaction_cost_pct/100.0; entry_notional=quantity*effective_price; entry_fee=entry_notional*fee_rate; total_outflow=entry_notional+entry_fee
        if total_outflow>account.cash+1e-9: raise ValueError("Manual paper entry would exceed available cash.")
        cash_before=account.cash; account.cash=max(account.cash-total_outflow,0.0)
        position=PaperPosition(symbol=strategy.symbol,timeframe=strategy.timeframe,entry_signal_timestamp=strategy.timestamp,entry_timestamp=timestamp,entry_price=effective_price,quantity=quantity,entry_notional=entry_notional,entry_transaction_cost=entry_fee,entry_assessment=strategy.assessment.value,cash_before_entry=cash_before,cash_after_entry=account.cash,stop_loss_price=stop_loss_price,entry_mode="MANUAL_GUARDED")
        account.open_positions.append(position); account.sync_legacy_position(); account.total_transaction_cost+=entry_fee
        return account

    def sell(self, *, symbol: str, execution_price: float, timestamp: datetime) -> PaperAccount:
        account=self.paper_service.state(); position=account.position_for(symbol)
        if not account.active or position is None: raise ValueError(f"There is no active paper position for {symbol} to SELL.")
        if execution_price<=0: raise ValueError("Manual exit price must be positive.")
        effective_price=float(execution_price)*(1.0-account.config.slippage_pct/100.0)
        exit_notional=position.quantity*effective_price; exit_fee=exit_notional*(account.config.transaction_cost_pct/100.0)
        gross_pnl=(effective_price-position.entry_price)*position.quantity; total_fee=position.entry_transaction_cost+exit_fee; net_pnl=gross_pnl-total_fee
        equity_before=account.realized_equity; account.cash+=exit_notional-exit_fee; account.realized_equity+=net_pnl
        committed_capital=position.entry_notional+position.entry_transaction_cost
        if committed_capital<=0: raise ValueError("Committed capital must be positive.")
        account.closed_trades.append(PaperTrade(symbol=position.symbol,timeframe=position.timeframe,entry_signal_timestamp=position.entry_signal_timestamp,entry_timestamp=position.entry_timestamp,entry_price=position.entry_price,exit_signal_timestamp=timestamp,exit_timestamp=timestamp,exit_price=effective_price,quantity=position.quantity,entry_notional=position.entry_notional,exit_notional=exit_notional,gross_pnl=gross_pnl,entry_transaction_cost=position.entry_transaction_cost,exit_transaction_cost=exit_fee,transaction_cost=total_fee,net_pnl=net_pnl,return_pct=(net_pnl/committed_capital)*100.0,equity_before=equity_before,equity_after=account.realized_equity,entry_assessment=position.entry_assessment,exit_assessment="MANUAL_SELL",exit_reason=PaperExitReason.MANUAL,entry_mode=position.entry_mode))
        account.total_transaction_cost+=exit_fee; account.open_positions=[item for item in account.open_positions if item.symbol!=symbol]; account.sync_legacy_position(); account.peak_realized_equity=max(account.peak_realized_equity,account.realized_equity)
        return account
