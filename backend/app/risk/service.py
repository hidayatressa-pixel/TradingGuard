from __future__ import annotations

from backend.app.strategy.models import Assessment, StrategyResult

from .models import RiskContext, RiskDecision, RiskEvidence, RiskPolicy, RiskResult, RiskStatus


class RiskService:
    """Deterministic safety gate that may veto strategy results without executing trades."""

    def evaluate(self, strategy: StrategyResult, context: RiskContext, policy: RiskPolicy) -> RiskResult:
        if strategy.data_ready is False or strategy.assessment == Assessment.INSUFFICIENT_DATA:
            evidence = [
                RiskEvidence(
                    rule="strategy_data_ready",
                    status=RiskStatus.BLOCK,
                    value=strategy.data_ready,
                    threshold=True,
                    description="Required strategy data is unavailable.",
                )
            ]
            return RiskResult(
                timestamp=strategy.timestamp,
                symbol=strategy.symbol,
                timeframe=strategy.timeframe,
                strategy_assessment=strategy.assessment.value,
                strategy_score=strategy.score,
                decision=RiskDecision.BLOCK,
                data_ready=False,
                evidence=evidence,
                block_reasons=["Required strategy data is unavailable."],
                warning_reasons=[],
            )

        evidence: list[RiskEvidence] = []
        block_reasons: list[str] = []
        warning_reasons: list[str] = []

        if not context.trading_enabled:
            evidence.append(
                RiskEvidence(
                    rule="manual_kill_switch",
                    status=RiskStatus.BLOCK,
                    value=context.trading_enabled,
                    threshold=True,
                    description="Manual kill switch is disabled.",
                )
            )
            block_reasons.append("Manual kill switch is disabled.")

        rules = [
            (
                "risk_per_trade",
                context.risk_per_trade_pct,
                policy.warning_risk_per_trade_pct,
                policy.max_risk_per_trade_pct,
                "risk per trade",
                True,
            ),
            (
                "daily_loss",
                context.daily_loss_pct,
                policy.warning_daily_loss_pct,
                policy.max_daily_loss_pct,
                "daily loss",
                False,
            ),
            (
                "total_exposure",
                context.total_exposure_pct,
                policy.warning_total_exposure_pct,
                policy.max_total_exposure_pct,
                "total exposure",
                True,
            ),
            (
                "open_positions",
                float(context.open_positions),
                float(policy.warning_open_positions),
                float(policy.max_open_positions),
                "open positions",
                False,
            ),
            (
                "drawdown",
                context.current_drawdown_pct,
                policy.warning_drawdown_pct,
                policy.max_drawdown_pct,
                "drawdown",
                False,
            ),
        ]

        for rule_name, value, warning_threshold, hard_threshold, description, hard_limit_is_exclusive in rules:
            if hard_limit_is_exclusive:
                is_block = value > hard_threshold
            else:
                is_block = value >= hard_threshold

            if is_block:
                evidence.append(
                    RiskEvidence(
                        rule=rule_name,
                        status=RiskStatus.BLOCK,
                        value=value,
                        threshold=hard_threshold,
                        description=f"{description} exceeded hard limit.",
                    )
                )
                block_reasons.append(f"{description.capitalize()} exceeded hard limit.")
            elif value >= warning_threshold:
                evidence.append(
                    RiskEvidence(
                        rule=rule_name,
                        status=RiskStatus.WARNING,
                        value=value,
                        threshold=warning_threshold,
                        description=f"{description} is at or beyond warning threshold.",
                    )
                )
                warning_reasons.append(f"{description.capitalize()} is at or beyond warning threshold.")
            else:
                evidence.append(
                    RiskEvidence(
                        rule=rule_name,
                        status=RiskStatus.PASS,
                        value=value,
                        threshold=warning_threshold,
                        description=f"{description} is within allowed limits.",
                    )
                )

        if block_reasons:
            decision = RiskDecision.BLOCK
        elif warning_reasons:
            decision = RiskDecision.WARNING
        else:
            decision = RiskDecision.ALLOW

        result = RiskResult(
            timestamp=strategy.timestamp,
            symbol=strategy.symbol,
            timeframe=strategy.timeframe,
            strategy_assessment=strategy.assessment.value,
            strategy_score=strategy.score,
            decision=decision,
            data_ready=strategy.data_ready,
            evidence=evidence,
            block_reasons=block_reasons,
            warning_reasons=warning_reasons,
        )
        return result
