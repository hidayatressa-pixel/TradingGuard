from __future__ import annotations

import math
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PaperTradingConfig(BaseModel):
    model_config = ConfigDict(strict=True)
    initial_capital: float = 10000.0
    position_size_pct: float = 10.0
    transaction_cost_pct: float = 0.10
    slippage_pct: float = 0.05
    paper_trading_enabled: bool = True

    @field_validator("initial_capital", "position_size_pct", "transaction_cost_pct", "slippage_pct")
    @classmethod
    def validate_finite(cls, value: float) -> float:
        if not math.isfinite(value): raise ValueError("numeric configuration values must be finite.")
        return value

    @model_validator(mode="after")
    def validate_config(self) -> "PaperTradingConfig":
        if self.initial_capital <= 0: raise ValueError("initial_capital must be greater than zero.")
        if not 0 < self.position_size_pct <= 100: raise ValueError("position_size_pct must be between 0 and 100.")
        if self.transaction_cost_pct < 0: raise ValueError("transaction_cost_pct must be non-negative.")
        if self.slippage_pct < 0: raise ValueError("slippage_pct must be non-negative.")
        return self


class PendingActionType(str, Enum): ENTRY="ENTRY"; EXIT="EXIT"
class PaperExitReason(str, Enum): STRATEGY="STRATEGY"; STOP_LOSS="STOP_LOSS"; MANUAL="MANUAL"


class PendingEntry(BaseModel):
    model_config=ConfigDict(strict=True)
    action:PendingActionType=PendingActionType.ENTRY; signal_timestamp:datetime; symbol:str; timeframe:str; assessment:str; execute_index:int; stop_loss_price:float|None=None; quantity:float|None=None

    @field_validator("stop_loss_price", "quantity")
    @classmethod
    def validate_optional_positive_finite(cls,value:float|None)->float|None:
        if value is not None and (not math.isfinite(value) or value<=0): raise ValueError("stop_loss_price and quantity must be finite and positive when supplied.")
        return value


class PendingExit(BaseModel):
    model_config=ConfigDict(strict=True); action:PendingActionType=PendingActionType.EXIT; signal_timestamp:datetime; symbol:str; timeframe:str; assessment:str; execute_index:int


class PaperPosition(BaseModel):
    model_config=ConfigDict(strict=True)
    symbol:str; timeframe:str; entry_signal_timestamp:datetime; entry_timestamp:datetime; entry_price:float; quantity:float; entry_notional:float; entry_transaction_cost:float; entry_assessment:str; cash_before_entry:float; cash_after_entry:float; stop_loss_price:float|None=None; entry_mode:str="AUTO"


class PaperTrade(BaseModel):
    model_config=ConfigDict(strict=True)
    symbol:str; timeframe:str; entry_signal_timestamp:datetime; entry_timestamp:datetime; entry_price:float; exit_signal_timestamp:datetime; exit_timestamp:datetime; exit_price:float; quantity:float; entry_notional:float; exit_notional:float; gross_pnl:float; entry_transaction_cost:float; exit_transaction_cost:float; transaction_cost:float; net_pnl:float; return_pct:float; equity_before:float; equity_after:float; entry_assessment:str; exit_assessment:str; exit_reason:PaperExitReason=PaperExitReason.STRATEGY; entry_mode:str="AUTO"


class PaperPerformanceSnapshot(BaseModel):
    model_config=ConfigDict(strict=True)
    initial_capital:float; realized_equity:float; realized_net_profit:float; realized_return_pct:float; total_closed_trades:int; winning_trades:int; losing_trades:int; breakeven_trades:int; win_rate_pct:float; gross_profit:float; gross_loss:float; profit_factor:float|None; average_trade_pnl:float; expected_value:float; total_transaction_cost:float; open_position:PaperPosition|None; pending_action:PendingEntry|PendingExit|None


class PaperAccount(BaseModel):
    model_config=ConfigDict(strict=True)
    config:PaperTradingConfig; active:bool=False; initial_capital:float; cash:float; realized_equity:float; peak_realized_equity:float; day_start_equity:float; risk_day:str|None=None
    open_position:PaperPosition|None=None; closed_trades:list[PaperTrade]=Field(default_factory=list); total_transaction_cost:float=0.0; pending_entry:PendingEntry|None=None; pending_exit:PendingExit|None=None; last_event_timestamp:datetime|None=None; event_index:int=0

    @model_validator(mode="after")
    def validate_state(self)->"PaperAccount":
        if self.pending_entry is not None and self.pending_exit is not None: raise ValueError("paper account cannot have pending entry and exit actions together.")
        for value in (self.initial_capital,self.cash,self.realized_equity,self.peak_realized_equity,self.day_start_equity,self.total_transaction_cost):
            if not math.isfinite(value): raise ValueError("paper account numeric values must be finite.")
        if self.initial_capital <= 0 or self.peak_realized_equity <= 0 or self.day_start_equity <= 0: raise ValueError("paper account equity baselines must be positive.")
        if self.peak_realized_equity < self.realized_equity: raise ValueError("peak_realized_equity cannot be below realized_equity.")
        return self

    @property
    def pending_action(self)->PendingEntry|PendingExit|None: return self.pending_entry or self.pending_exit

    def performance(self)->PaperPerformanceSnapshot:
        trades=self.closed_trades; winning=sum(1 for trade in trades if trade.net_pnl>0); losing=sum(1 for trade in trades if trade.net_pnl<0); gross_profit=sum(max(trade.net_pnl,0.0) for trade in trades); gross_loss=sum(abs(min(trade.net_pnl,0.0)) for trade in trades); total=len(trades); average=sum(trade.net_pnl for trade in trades)/total if total else 0.0
        return PaperPerformanceSnapshot(initial_capital=self.initial_capital,realized_equity=self.realized_equity,realized_net_profit=self.realized_equity-self.initial_capital,realized_return_pct=((self.realized_equity-self.initial_capital)/self.initial_capital)*100.0,total_closed_trades=total,winning_trades=winning,losing_trades=losing,breakeven_trades=total-winning-losing,win_rate_pct=(winning/total)*100.0 if total else 0.0,gross_profit=gross_profit,gross_loss=gross_loss,profit_factor=(gross_profit/gross_loss) if gross_loss>0 else None,average_trade_pnl=average,expected_value=average,total_transaction_cost=self.total_transaction_cost,open_position=self.open_position,pending_action=self.pending_action)
