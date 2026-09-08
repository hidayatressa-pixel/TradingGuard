from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.paper.models import PaperAccount
from backend.app.risk.context import PaperRiskContextBuilder, RiskContextAvailability
from backend.app.risk.models import RiskDecision, RiskEvidence, RiskPolicy, RiskResult, RiskStatus
from backend.app.risk.service import RiskService
from backend.app.risk_sizing.models import RiskSizingRequest, RiskSizingResult
from backend.app.risk_sizing.service import RiskSizingService
from backend.app.strategy.models import StrategyResult


class ProspectiveRiskGateResult(BaseModel):
    model_config = ConfigDict(strict=True)

    sizing: RiskSizingResult
    context_availability: RiskContextAvailability
    risk: RiskResult | None = None
    execution_permission_established: bool
    reason: str
    recommendations: list[str] = []


class ProspectiveRiskGateService:
    """Orchestrate sizing -> authoritative context -> Risk Guard without executing trades."""

    def __init__(self) -> None:
        self.sizing_service = RiskSizingService()
        self.context_builder = PaperRiskContextBuilder()
        self.risk_service = RiskService()

    @staticmethod
    def _format_value(evidence: RiskEvidence) -> str:
        if isinstance(evidence.value, bool):
            return "ON" if evidence.value else "OFF"
        value = float(evidence.value)
        if evidence.rule == "open_positions":
            return str(int(value))
        return f"{value:.2f}%"

    @staticmethod
    def _format_threshold(evidence: RiskEvidence) -> str:
        threshold = evidence.threshold
        if threshold is None:
            return "N/A"
        if isinstance(threshold, bool):
            return "ON" if threshold else "OFF"
        value = float(threshold)
        if evidence.rule == "open_positions":
            return str(int(value))
        return f"{value:.2f}%"

    @classmethod
    def _reason(cls, risk: RiskResult) -> str:
        failed = [item for item in risk.evidence if item.status in {RiskStatus.WARNING, RiskStatus.BLOCK}]
        if not failed:
            return (
                f"Market {risk.strategy_assessment} (score {risk.strategy_score:+d}). "
                "Semua parameter Risk Guard berada dalam batas; entry diizinkan."
            )
        details = "; ".join(
            f"{item.rule.replace('_', ' ')} {cls._format_value(item)} "
            f"(batas {item.status.value.lower()} {cls._format_threshold(item)})"
            for item in failed
        )
        return (
            f"Market {risk.strategy_assessment} (score {risk.strategy_score:+d}) tetap valid sebagai konteks teknikal, "
            f"tetapi Risk Guard {risk.decision.value}: {details}."
        )

    @classmethod
    def _recommendations(cls, risk: RiskResult) -> list[str]:
        recommendations: list[str] = []
        for item in risk.evidence:
            if item.status not in {RiskStatus.WARNING, RiskStatus.BLOCK}:
                continue
            threshold = cls._format_threshold(item)
            if item.rule == "risk_per_trade":
                recommendations.append(f"Turunkan risk budget per trade hingga di bawah {threshold}, lalu evaluasi ulang.")
            elif item.rule == "total_exposure":
                recommendations.append(f"Kurangi alokasi entry atau tutup sebagian exposure sampai total exposure di bawah {threshold}.")
            elif item.rule == "open_positions":
                recommendations.append(f"Kurangi jumlah posisi terbuka hingga di bawah {threshold} sebelum menambah posisi baru.")
            elif item.rule == "daily_loss":
                recommendations.append("Jangan menaikkan limit untuk memaksa entry; hentikan penambahan risiko dan tunggu risk-day berikutnya.")
            elif item.rule == "drawdown":
                recommendations.append("Kurangi exposure dan jangan menambah risiko sampai drawdown kembali di bawah batas engine.")
            elif item.rule == "manual_kill_switch":
                recommendations.append("Trading dinonaktifkan oleh kill switch; jangan bypass interlock tanpa pemeriksaan manual.")
            elif item.rule == "strategy_data_ready":
                recommendations.append("Tunggu data strategy lengkap; jangan entry dengan data teknikal yang belum valid.")
        return recommendations

    def evaluate(
        self,
        strategy: StrategyResult,
        account: PaperAccount,
        sizing_request: RiskSizingRequest,
        policy: RiskPolicy | None = None,
    ) -> ProspectiveRiskGateResult:
        sizing = self.sizing_service.evaluate(sizing_request)
        context_availability = self.context_builder.build(account, sizing.risk_per_trade_pct)

        if not context_availability.available or context_availability.context is None:
            return ProspectiveRiskGateResult(
                sizing=sizing,
                context_availability=context_availability,
                risk=None,
                execution_permission_established=False,
                reason="Risk Guard tidak dievaluasi karena authoritative RiskContext belum lengkap.",
                recommendations=["Lengkapi atau pulihkan RiskContext sebelum mencoba entry kembali."],
            )

        risk = self.risk_service.evaluate(strategy, context_availability.context, policy or RiskPolicy())
        return ProspectiveRiskGateResult(
            sizing=sizing,
            context_availability=context_availability,
            risk=risk,
            execution_permission_established=risk.decision == RiskDecision.ALLOW,
            reason=self._reason(risk),
            recommendations=self._recommendations(risk),
        )
