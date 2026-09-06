from __future__ import annotations

from backend.app.market.models import Candle
from backend.app.strategy.models import Assessment, StrategyResult

from .models import BacktestConfig, BacktestResult, BacktestTrade, EquityCurvePoint


class BacktestService:
    """Runs deterministic historical simulation with long-only, no-lookahead execution."""

    def _validate_alignment(self, candles: list[Candle], strategy_results: list[StrategyResult]) -> None:
        if not candles or not strategy_results:
            raise ValueError("Candles and strategy results datasets must not be empty.")
        if len(candles) != len(strategy_results):
            raise ValueError("Candles and strategy results must be aligned, with one strategy result per candle.")

        candle_timestamps = [candle.timestamp for candle in candles]
        if len(set(candle_timestamps)) != len(candle_timestamps):
            raise ValueError("Duplicate candle timestamps detected.")
        strategy_timestamps = [result.timestamp for result in strategy_results]
        if len(set(strategy_timestamps)) != len(strategy_timestamps):
            raise ValueError("Duplicate strategy timestamps detected.")

        for previous, current in zip(candles, candles[1:]):
            if current.timestamp <= previous.timestamp:
                raise ValueError("Candles are not in chronological order.")
        for previous, current in zip(strategy_results, strategy_results[1:]):
            if current.timestamp <= previous.timestamp:
                raise ValueError("Strategy results are not in chronological order.")

        for candle, strategy in zip(candles, strategy_results):
            if candle.timestamp != strategy.timestamp:
                raise ValueError("Strategy result timestamp does not match the candle timestamp.")
            if candle.symbol != strategy.symbol:
                raise ValueError("Candles and strategy results do not match on symbol.")
            if candle.timeframe != strategy.timeframe:
                raise ValueError("Candles and strategy results do not match on timeframe.")

    def _is_long_signal(self, strategy: StrategyResult) -> bool:
        return strategy.data_ready and strategy.assessment in {
            Assessment.BULLISH,
            Assessment.STRONG_BULLISH,
        }

    def _is_exit_signal(self, strategy: StrategyResult) -> bool:
        return strategy.data_ready and strategy.assessment in {
            Assessment.NEUTRAL,
            Assessment.BEARISH,
            Assessment.STRONG_BEARISH,
        }

    def _compute_quantity(
        self,
        effective_entry_price: float,
        equity_before: float,
        position_size_pct: float,
        transaction_cost_pct: float,
    ) -> float:
        if effective_entry_price <= 0:
            raise ValueError("Entry price must be positive.")
        target_allocation = equity_before * (position_size_pct / 100.0)
        if target_allocation <= 0:
            raise ValueError("Target allocation must be positive.")

        scale = 1.0 + (transaction_cost_pct / 100.0)
        quantity = target_allocation / (effective_entry_price * scale)
        if quantity <= 0:
            raise ValueError("Computed position quantity must be positive.")
        return quantity

    def _close_trade(
        self,
        candles: list[Candle],
        trade_index: int,
        position: dict,
        config: BacktestConfig,
        current_equity: float,
        forced_exit: bool,
        exit_signal_timestamp=None,
        exit_assessment: str | None = None,
    ) -> tuple[BacktestTrade, float, EquityCurvePoint]:
        if forced_exit:
            raw_exit_price = float(candles[-1].close)
            exit_timestamp = candles[-1].timestamp
            resolved_exit_signal_timestamp = candles[-1].timestamp
            resolved_exit_assessment = "FORCED_EXIT"
        else:
            raw_exit_price = float(candles[trade_index].open)
            exit_timestamp = candles[trade_index].timestamp
            resolved_exit_signal_timestamp = exit_signal_timestamp
            resolved_exit_assessment = exit_assessment

        effective_exit_price = raw_exit_price * (1.0 - (config.slippage_pct / 100.0))
        exit_notional = position["quantity"] * effective_exit_price
        exit_transaction_cost = exit_notional * (config.transaction_cost_pct / 100.0)
        gross_pnl = position["quantity"] * (effective_exit_price - position["entry_price"])
        transaction_cost = position["entry_transaction_cost"] + exit_transaction_cost
        net_pnl = gross_pnl - transaction_cost

        equity_before = current_equity
        equity_after = current_equity + net_pnl

        trade = BacktestTrade(
            entry_signal_timestamp=position["entry_signal_timestamp"],
            entry_timestamp=position["entry_timestamp"],
            entry_price=position["entry_price"],
            exit_signal_timestamp=resolved_exit_signal_timestamp,
            exit_timestamp=exit_timestamp,
            exit_price=effective_exit_price,
            quantity=position["quantity"],
            gross_pnl=gross_pnl,
            entry_transaction_cost=position["entry_transaction_cost"],
            exit_transaction_cost=exit_transaction_cost,
            transaction_cost=transaction_cost,
            net_pnl=net_pnl,
            return_pct=(net_pnl / position["entry_equity_basis"]) if position["entry_equity_basis"] else 0.0,
            equity_before=equity_before,
            equity_after=equity_after,
            entry_assessment=position["entry_assessment"],
            exit_assessment=resolved_exit_assessment,
            forced_exit=forced_exit,
        )
        equity_curve_point = EquityCurvePoint(timestamp=exit_timestamp, equity=equity_after)
        return trade, equity_after, equity_curve_point

    def evaluate(
        self,
        candles: list[Candle],
        strategy_results: list[StrategyResult],
        config: BacktestConfig | None = None,
    ) -> BacktestResult:
        self._validate_alignment(candles, strategy_results)
        active_config = config or BacktestConfig()

        realized_equity = float(active_config.initial_capital)
        equity_curve = [EquityCurvePoint(timestamp=candles[0].timestamp, equity=realized_equity)]
        trades: list[BacktestTrade] = []
        pending_entry: dict | None = None
        pending_exit: dict | None = None
        position: dict | None = None

        for index in range(len(candles)):
            current_strategy = strategy_results[index]

            if pending_entry is not None and index == pending_entry["execute_index"]:
                raw_entry_price = float(candles[index].open)
                effective_entry_price = raw_entry_price * (1.0 + (active_config.slippage_pct / 100.0))
                quantity = self._compute_quantity(
                    effective_entry_price,
                    realized_equity,
                    active_config.position_size_pct,
                    active_config.transaction_cost_pct,
                )
                entry_notional = quantity * effective_entry_price
                entry_transaction_cost = entry_notional * (active_config.transaction_cost_pct / 100.0)
                entry_total_outflow = entry_notional + entry_transaction_cost

                position = {
                    "entry_signal_timestamp": pending_entry["signal_timestamp"],
                    "entry_timestamp": candles[index].timestamp,
                    "entry_price": effective_entry_price,
                    "quantity": quantity,
                    "entry_transaction_cost": entry_transaction_cost,
                    "entry_assessment": pending_entry["assessment"],
                    "entry_equity_basis": entry_total_outflow,
                }
                pending_entry = None

            if position is not None and pending_exit is not None and index == pending_exit["execute_index"]:
                trade, realized_equity, curve_point = self._close_trade(
                    candles,
                    index,
                    position,
                    active_config,
                    realized_equity,
                    forced_exit=False,
                    exit_signal_timestamp=pending_exit["signal_timestamp"],
                    exit_assessment=pending_exit["assessment"],
                )
                trades.append(trade)
                equity_curve.append(curve_point)
                position = None
                pending_exit = None
                continue

            if position is not None:
                if pending_exit is None and index + 1 < len(candles) and self._is_exit_signal(current_strategy):
                    pending_exit = {
                        "signal_timestamp": current_strategy.timestamp,
                        "execute_index": index + 1,
                        "assessment": current_strategy.assessment.value,
                    }
                elif index == len(candles) - 1:
                    trade, realized_equity, curve_point = self._close_trade(
                        candles,
                        index,
                        position,
                        active_config,
                        realized_equity,
                        forced_exit=True,
                    )
                    trades.append(trade)
                    equity_curve.append(curve_point)
                    position = None
                    pending_exit = None

            if pending_entry is None and position is None and index + 1 < len(candles) and self._is_long_signal(current_strategy):
                pending_entry = {
                    "signal_timestamp": current_strategy.timestamp,
                    "execute_index": index + 1,
                    "assessment": current_strategy.assessment.value,
                }

        if position is not None:
            trade, realized_equity, curve_point = self._close_trade(
                candles,
                len(candles) - 1,
                position,
                active_config,
                realized_equity,
                forced_exit=True,
            )
            trades.append(trade)
            equity_curve.append(curve_point)

        total_trades = len(trades)
        winning_trades = sum(1 for trade in trades if trade.net_pnl > 0)
        losing_trades = sum(1 for trade in trades if trade.net_pnl < 0)
        breakeven_trades = sum(1 for trade in trades if trade.net_pnl == 0)
        gross_profit = sum(max(trade.net_pnl, 0.0) for trade in trades)
        gross_loss = sum(abs(min(trade.net_pnl, 0.0)) for trade in trades)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
        average_trade_pnl = sum(trade.net_pnl for trade in trades) / total_trades if total_trades else 0.0
        average_win = sum(trade.net_pnl for trade in trades if trade.net_pnl > 0) / max(winning_trades, 1) if winning_trades else 0.0
        average_loss = sum(trade.net_pnl for trade in trades if trade.net_pnl < 0) / max(losing_trades, 1) if losing_trades else 0.0
        expected_value = average_trade_pnl
        largest_win = max((trade.net_pnl for trade in trades if trade.net_pnl > 0), default=0.0)
        largest_loss = min((trade.net_pnl for trade in trades if trade.net_pnl < 0), default=0.0)
        total_transaction_cost = sum(trade.transaction_cost for trade in trades)

        peak_equity = float(active_config.initial_capital)
        max_drawdown_pct = 0.0
        for point in equity_curve:
            if point.equity > peak_equity:
                peak_equity = point.equity
            if peak_equity > 0:
                drawdown_pct = ((peak_equity - point.equity) / peak_equity) * 100.0
                max_drawdown_pct = max(max_drawdown_pct, max(drawdown_pct, 0.0))

        final_equity = equity_curve[-1].equity if equity_curve else float(active_config.initial_capital)
        net_profit = final_equity - float(active_config.initial_capital)
        total_return_pct = (net_profit / float(active_config.initial_capital)) * 100.0 if active_config.initial_capital else 0.0
        win_rate_pct = (winning_trades / total_trades) * 100.0 if total_trades else 0.0

        return BacktestResult(
            symbol=candles[0].symbol,
            timeframe=candles[0].timeframe,
            initial_capital=active_config.initial_capital,
            final_equity=final_equity,
            net_profit=net_profit,
            total_return_pct=total_return_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            breakeven_trades=breakeven_trades,
            win_rate_pct=win_rate_pct,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            average_trade_pnl=average_trade_pnl,
            average_win=average_win,
            average_loss=average_loss,
            expected_value=expected_value,
            max_drawdown_pct=max_drawdown_pct,
            largest_win=largest_win,
            largest_loss=largest_loss,
            total_transaction_cost=total_transaction_cost,
            trades=trades,
            equity_curve=equity_curve,
        )
