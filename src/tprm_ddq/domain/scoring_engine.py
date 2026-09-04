"""The deterministic inherent/residual risk-scoring engine (the vertical's consequential core).

Pure stdlib, frozen policy, explicit ``as_of``. Inherent risk is a weighted sum of policy
factors (service criticality, data classification, jurisdiction, substitutability); residual
risk is the inherent points reduced by evidenced control effectiveness in the ledger. Every
weight and threshold is a config policy block, so every number is adopter-owned.

Hard signals raise the band and can never be softened by narrative: a sanctions-category
adverse-media hit forces CRITICAL; an adverse SOC 2 opinion, an expired certificate, a going-concern
failure or a critical financial ratio each raise the residual band by one. The model may narrate the
result; it may never produce a band (cdd-sow-research's ``risk_service`` rule).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .evidence_ledger import EvidenceLedger
from .kernel import Severity
from .tprm_models import (
    EFFECTIVENESS_RANK,
    SEVERITY_RANK,
    CanonicalControl,
    ControlEffectiveness,
    DataClassification,
    FactorScore,
    FinancialStatus,
    MediaCategory,
    MediaFinding,
    Substitutability,
    VendorProfile,
)

_RANK_TO_SEVERITY: tuple[Severity, ...] = (
    Severity.LOW,
    Severity.MEDIUM,
    Severity.HIGH,
    Severity.CRITICAL,
)


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    """Weights, thresholds and control credit. Every value is the adopter's to set."""

    weight_criticality: int = 4
    weight_data: int = 3
    weight_jurisdiction: int = 2
    weight_substitutability: int = 2
    #: Data classification -> its inherent severity band.
    data_band: dict[DataClassification, Severity] = field(
        default_factory=lambda: {
            DataClassification.PUBLIC: Severity.LOW,
            DataClassification.INTERNAL: Severity.LOW,
            DataClassification.CONFIDENTIAL: Severity.HIGH,
            DataClassification.RESTRICTED: Severity.CRITICAL,
        }
    )
    #: Substitutability -> its inherent severity band.
    substitutability_band: dict[Substitutability, Severity] = field(
        default_factory=lambda: {
            Substitutability.COMMODITY: Severity.LOW,
            Substitutability.MODERATE: Severity.MEDIUM,
            Substitutability.SPECIALISED: Severity.HIGH,
            Substitutability.SOLE_SOURCE: Severity.CRITICAL,
        }
    )
    #: Jurisdictions carrying elevated inherent risk (residency, enforceability). Adopter-owned.
    high_risk_jurisdictions: frozenset[str] = field(
        default_factory=lambda: frozenset({"XX", "ZZ", "offshore-unnamed"})
    )
    #: Inherent points at or above each entry map to that band. Descending, checked in order.
    inherent_thresholds: tuple[tuple[int, Severity], ...] = (
        (30, Severity.CRITICAL),
        (22, Severity.HIGH),
        (12, Severity.MEDIUM),
        (0, Severity.LOW),
    )
    #: The controls whose evidenced effectiveness earns a residual reduction.
    credited_controls: tuple[CanonicalControl, ...] = (
        CanonicalControl.ACCESS_CONTROL,
        CanonicalControl.ENCRYPTION,
        CanonicalControl.INCIDENT_RESPONSE,
        CanonicalControl.BUSINESS_CONTINUITY,
        CanonicalControl.DATA_GOVERNANCE,
        CanonicalControl.LOGGING_MONITORING,
    )
    #: Points credited per unit of effectiveness rank (0..4) for each credited control.
    credit_per_effectiveness_rank: int = 1

    def band_for_points(self, points: int) -> Severity:
        for floor, band in self.inherent_thresholds:
            if points >= floor:
                return band
        return Severity.LOW


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """The scoring outcome: both bands, the arithmetic, and the hard signals that fired."""

    inherent_band: Severity
    residual_band: Severity
    inherent_points: int
    residual_points: int
    factors: tuple[FactorScore, ...]
    hard_signals: tuple[str, ...]


def _raise_band(band: Severity, steps: int = 1) -> Severity:
    rank = min(SEVERITY_RANK[band] + steps, len(_RANK_TO_SEVERITY) - 1)
    return _RANK_TO_SEVERITY[rank]


def _jurisdiction_band(profile: VendorProfile, policy: ScoringPolicy) -> Severity:
    return Severity.HIGH if profile.jurisdiction in policy.high_risk_jurisdictions else Severity.LOW


def score_vendor(
    profile: VendorProfile,
    ledger: EvidenceLedger,
    media: tuple[MediaFinding, ...],
    financials: FinancialStatus | None,
    *,
    as_of: date,
    policy: ScoringPolicy | None = None,
) -> ScoreResult:
    """Compute inherent and residual risk deterministically. Same inputs, same result."""
    _ = as_of  # explicit: the engine takes no clock; every date-sensitive read is passed in.
    pol = policy or ScoringPolicy()

    factors = (
        _factor("service_criticality", profile.service_criticality, pol.weight_criticality),
        _factor("data_classification", pol.data_band[profile.data_classification], pol.weight_data),
        _factor("jurisdiction", _jurisdiction_band(profile, pol), pol.weight_jurisdiction),
        _factor(
            "substitutability",
            pol.substitutability_band[profile.substitutability],
            pol.weight_substitutability,
        ),
    )
    inherent_points = sum(f.points for f in factors)
    inherent_band = pol.band_for_points(inherent_points)

    credit = 0
    for control in pol.credited_controls:
        effectiveness = ledger.best_effectiveness(control)
        credit += EFFECTIVENESS_RANK[effectiveness] * pol.credit_per_effectiveness_rank
    residual_points = max(inherent_points - credit, 0)
    residual_band = pol.band_for_points(residual_points)

    residual_band, hard_signals = _apply_hard_signals(residual_band, ledger, media, financials)

    return ScoreResult(
        inherent_band=inherent_band,
        residual_band=residual_band,
        inherent_points=inherent_points,
        residual_points=residual_points,
        factors=factors,
        hard_signals=hard_signals,
    )


def _factor(name: str, band: Severity, weight: int) -> FactorScore:
    points = SEVERITY_RANK[band] * weight
    return FactorScore(name=name, band=band, weight=weight, points=points)


def _apply_hard_signals(
    residual_band: Severity,
    ledger: EvidenceLedger,
    media: tuple[MediaFinding, ...],
    financials: FinancialStatus | None,
) -> tuple[Severity, tuple[str, ...]]:
    """Raise the residual band for each hard signal. Sanctions forces CRITICAL outright."""
    signals: list[str] = []
    band = residual_band

    if any(m.category == MediaCategory.SANCTIONS for m in media):
        signals.append("sanctions-category adverse media")
        band = Severity.CRITICAL
    if ledger.adverse_opinions():
        signals.append("adverse SOC 2 opinion")
        band = _raise_band(band)
    if ledger.expired_items():
        signals.append("expired certification")
        band = _raise_band(band)
    if financials is not None:
        if not financials.going_concern:
            signals.append("going-concern doubt")
            band = _raise_band(band)
        if financials.liquidity == Severity.CRITICAL or financials.leverage == Severity.CRITICAL:
            signals.append("critical financial ratio")
            band = _raise_band(band)

    return band, tuple(signals)


def is_effective(effectiveness: ControlEffectiveness) -> bool:
    """Whether a control reading counts as operating effectively (for narrative helpers)."""
    return effectiveness == ControlEffectiveness.EFFECTIVE
