"""Deterministic technical indicator calculations for OHLCV candles."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class MACDResult:
    macd: list[float | None]
    signal: list[float | None]
    histogram: list[float | None]


def _validate_finite_sequence(values: Sequence[float], *, allow_empty: bool = False) -> None:
    if not allow_empty and not values:
        raise ValueError("Input values cannot be empty.")
    for value in values:
        if not math.isfinite(float(value)):
            raise ValueError("Input values must be finite numbers.")


def calculate_ema(values: Sequence[float], period: int) -> list[float | None]:
    """Return an EMA series with None values during warm-up, using SMA seed."""
    if period < 1:
        raise ValueError("period must be >= 1.")
    if not values:
        raise ValueError("Input values cannot be empty.")

    _validate_finite_sequence(values)

    if period > len(values):
        return [None for _ in values]

    multiplier = 2.0 / (period + 1.0)
    result: list[float | None] = [None for _ in values]

    first_window = list(values[:period])
    seed = sum(first_window) / period
    result[period - 1] = seed

    for index in range(period, len(values)):
        previous = result[index - 1]
        if previous is None:
            previous = seed
        current = float(values[index])
        result[index] = (current - previous) * multiplier + previous

    return result


def calculate_rsi(values: Sequence[float], period: int = 14) -> list[float | None]:
    """Return Wilder RSI values with None during warm-up. Flat markets resolve to 50."""
    if period < 1:
        raise ValueError("period must be >= 1.")
    if not values:
        raise ValueError("Input values cannot be empty.")
    _validate_finite_sequence(values)
    if any(float(value) <= 0 for value in values):
        raise ValueError("Prices must be positive.")

    result: list[float | None] = [None for _ in values]
    if len(values) <= period:
        return result

    changes = [float(values[index]) - float(values[index - 1]) for index in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [abs(min(change, 0.0)) for change in changes]

    initial_index = period
    seed_window = changes[:period]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0 and avg_gain > 0:
        result[initial_index] = 100.0
    elif avg_gain == 0 and avg_loss > 0:
        result[initial_index] = 0.0
    elif avg_gain == 0 and avg_loss == 0:
        result[initial_index] = 50.0
    else:
        relative_strength = avg_gain / avg_loss
        result[initial_index] = 100.0 - (100.0 / (1.0 + relative_strength))

    for index in range(initial_index + 1, len(values)):
        current_gain = max(changes[index - 1], 0.0)
        current_loss = abs(min(changes[index - 1], 0.0))
        avg_gain = ((avg_gain * (period - 1)) + current_gain) / period
        avg_loss = ((avg_loss * (period - 1)) + current_loss) / period

        if avg_loss == 0 and avg_gain > 0:
            result[index] = 100.0
        elif avg_gain == 0 and avg_loss > 0:
            result[index] = 0.0
        elif avg_gain == 0 and avg_loss == 0:
            result[index] = 50.0
        else:
            relative_strength = avg_gain / avg_loss
            result[index] = 100.0 - (100.0 / (1.0 + relative_strength))

    return result


def calculate_macd(
    values: Sequence[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> "MACDResult":
    """Return MACD, signal, and histogram aligned to the original values."""
    if fast_period < 1 or slow_period < 1 or signal_period < 1:
        raise ValueError("All MACD periods must be >= 1.")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period.")
    if not values:
        raise ValueError("Input values cannot be empty.")
    _validate_finite_sequence(values)

    fast_ema = calculate_ema(values, fast_period)
    slow_ema = calculate_ema(values, slow_period)

    macd_values: list[float | None] = [None for _ in values]
    for index in range(len(values)):
        if fast_ema[index] is not None and slow_ema[index] is not None:
            macd_values[index] = fast_ema[index] - slow_ema[index]

    signal_values = [None for _ in values]
    valid_macd = [value for value in macd_values if value is not None]
    if valid_macd:
        signal_ema = calculate_ema(valid_macd, signal_period)
        valid_positions = [index for index, value in enumerate(macd_values) if value is not None]
        for offset, index in enumerate(valid_positions):
            if offset < len(signal_ema):
                signal_values[index] = signal_ema[offset]

    histogram_values = [None for _ in values]
    for index in range(len(values)):
        if macd_values[index] is not None and signal_values[index] is not None:
            histogram_values[index] = macd_values[index] - signal_values[index]

    return MACDResult(
        macd=macd_values,
        signal=signal_values,
        histogram=histogram_values,
    )
