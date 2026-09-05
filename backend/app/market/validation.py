from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable

from .models import Candle


def validate_candle_dataset(candles: list[Candle] | Iterable[Candle]) -> list[str]:
    """Validate a candle dataset and return human-readable errors."""
    if candles is None:
        return ["Dataset is empty."]

    candle_list = list(candles)
    if not candle_list:
        return ["Dataset is empty."]

    errors: list[str] = []
    timestamps = [candle.timestamp for candle in candle_list]
    duplicate_keys = [timestamp for timestamp, count in Counter(timestamps).items() if count > 1]
    if duplicate_keys:
        errors.append(f"Duplicate timestamps detected: {duplicate_keys[:5]}.")

    for index, candle in enumerate(candle_list):
        if candle.high < candle.low:
            errors.append(f"Candle {index} has high < low.")
        if candle.high < max(candle.open, candle.close):
            errors.append(f"Candle {index} has high below open/close.")
        if candle.low > min(candle.open, candle.close):
            errors.append(f"Candle {index} has low above open/close.")
        if candle.volume < 0:
            errors.append(f"Candle {index} has negative volume.")
        if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
            errors.append(f"Candle {index} contains non-positive price data.")

    for previous, current in zip(candle_list, candle_list[1:]):
        if current.timestamp <= previous.timestamp:
            errors.append(
                f"Candles are not in chronological order: "
                f"{previous.timestamp.isoformat()} then {current.timestamp.isoformat()}."
            )

    return errors
