from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


class BacktestConfig(BaseModel):
    """Configuration for deterministic historical backtests."""

    model_config = ConfigDict(strict=True)

    initial_capital: float = 10000.0
    position_size_pct: float = 10.0
    transaction_cost_pct: float = 0.10
    slippage_pct: float = 0.05

    @model_validator(mode="after")
    def validate_config(self) -> "BacktestConfig":
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be greater than zero.")
        if not 0 < self.position_size_pct <= 100:
            raise ValueError("position_size_pct must be between 0 and 100, exclusive of zero.")
        if self.transaction_cost_pct < 0:
            raise ValueError("transaction_cost_pct must be non-negative.")
        if self.slippage_pct < 0:
            raise ValueError("slippage_pct must be non-negative.")
        return self


class EquityCurvePoint(BaseModel):
    """Realized equity value observed after completed trades."""

    model_config = ConfigDict(strict=True)

    timestamp: datetime
    equity: float


class BacktestTrade(BaseModel):
    """A single realized long-only trade executed in a historical simulation."""

    model_config = ConfigDict(strict=True)

    entry_signal_timestamp: datetime
    entry_timestamp: datetime
    entry_price: float
    exit_signal_timestamp: datetime
    exit_timestamp: datetime
    exit_price: float
    quantity: float
    gross_pnl: float
    entry_transaction_cost: float
    exit_transaction_cost: float
    transaction_cost: float
    net_pnl: float
    return_pct: float
    equity_before: float
    equity_after: float
    entry_assessment: str
    exit_assessment: str
    forced_exit: bool


class BacktestResult(BaseModel):
    """Deterministic aggregate metrics for a historical backtest."""

    model_config = ConfigDict(strict=True)

    symbol: str
    timeframe: str
    initial_capital: float
    final_equity: float
    net_profit: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate_pct: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    average_trade_pnl: float
    average_win: float
    average_loss: float
    expected_value: float
    max_drawdown_pct: float
    largest_win: float
    largest_loss: float
    total_transaction_cost: float
    trades: list[BacktestTrade]
    equity_curve: list[EquityCurvePoint]
