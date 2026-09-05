from __future__ import annotations

from backend.app.indicators.models import IndicatorSnapshot

from .models import Assessment, StrategyEvidence, StrategyResult


class StrategyService:
    """Evaluates market conditions from complete indicator snapshots without trading actions."""

    def _normalize_score(self, raw_score: int) -> int:
        if raw_score <= -5:
            return 0
        if raw_score >= 5:
            return 100
        return int(round(((raw_score + 5) / 10) * 100))

    def _assessment_for_score(self, raw_score: int) -> Assessment:
        if raw_score <= -4:
            return Assessment.STRONG_BEARISH
        if raw_score <= -2:
            return Assessment.BEARISH
        if raw_score <= 1:
            return Assessment.NEUTRAL
        if raw_score <= 3:
            return Assessment.BULLISH
        return Assessment.STRONG_BULLISH

    def evaluate_snapshot(self, snapshot: IndicatorSnapshot) -> StrategyResult:
        required_fields = [
            snapshot.ema_fast,
            snapshot.ema_slow,
            snapshot.rsi,
            snapshot.macd,
            snapshot.macd_signal,
        ]
        if any(value is None for value in required_fields):
            return StrategyResult(
                timestamp=snapshot.timestamp,
                symbol=snapshot.symbol,
                timeframe=snapshot.timeframe,
                score=0,
                normalized_score=0,
                assessment=Assessment.INSUFFICIENT_DATA,
                data_ready=False,
                evidence=[],
            )

        evidence: list[StrategyEvidence] = []

        if snapshot.ema_fast is not None and snapshot.ema_slow is not None:
            if snapshot.ema_fast > snapshot.ema_slow:
                contribution = 2
                condition = "ema_fast > ema_slow"
                description = "Fast EMA is above slow EMA."
            elif snapshot.ema_fast < snapshot.ema_slow:
                contribution = -2
                condition = "ema_fast < ema_slow"
                description = "Fast EMA is below slow EMA."
            else:
                contribution = 0
                condition = "ema_fast == ema_slow"
                description = "Fast EMA is equal to slow EMA."
            evidence.append(
                StrategyEvidence(
                    indicator="EMA",
                    condition=condition,
                    contribution=contribution,
                    description=description,
                )
            )

        if snapshot.rsi is not None:
            if snapshot.rsi >= 70:
                contribution = -1
                condition = "rsi >= 70"
                description = "RSI is overbought."
            elif snapshot.rsi <= 30:
                contribution = 1
                condition = "rsi <= 30"
                description = "RSI is oversold."
            else:
                contribution = 0
                condition = "30 < rsi < 70"
                description = "RSI is in the neutral range."
            evidence.append(
                StrategyEvidence(
                    indicator="RSI",
                    condition=condition,
                    contribution=contribution,
                    description=description,
                )
            )

        if snapshot.macd is not None and snapshot.macd_signal is not None:
            if snapshot.macd > snapshot.macd_signal:
                contribution = 2
                condition = "macd > macd_signal"
                description = "MACD is above signal line."
            elif snapshot.macd < snapshot.macd_signal:
                contribution = -2
                condition = "macd < macd_signal"
                description = "MACD is below signal line."
            else:
                contribution = 0
                condition = "macd == macd_signal"
                description = "MACD is equal to signal line."
            evidence.append(
                StrategyEvidence(
                    indicator="MACD",
                    condition=condition,
                    contribution=contribution,
                    description=description,
                )
            )

        raw_score = sum(item.contribution for item in evidence)
        normalized = self._normalize_score(raw_score)
        assessment = self._assessment_for_score(raw_score)
        return StrategyResult(
            timestamp=snapshot.timestamp,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            score=raw_score,
            normalized_score=normalized,
            assessment=assessment,
            data_ready=True,
            evidence=evidence,
        )

    def build_results(self, snapshots: list[IndicatorSnapshot]) -> list[StrategyResult]:
        if not snapshots:
            raise ValueError("Snapshots dataset is empty.")

        timestamps = [snapshot.timestamp for snapshot in snapshots]
        if len(set(timestamps)) != len(timestamps):
            raise ValueError("Duplicate timestamps detected.")
        for previous, current in zip(snapshots, snapshots[1:]):
            if current.timestamp <= previous.timestamp:
                raise ValueError("Snapshots are not in chronological order.")

        return [self.evaluate_snapshot(snapshot) for snapshot in snapshots]
