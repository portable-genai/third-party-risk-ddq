"""Unit tests for the deterministic TPRM engines: scoring, financials, contract diff, gaps.

The consequential numbers come from pure stdlib code, so these prove determinism (same inputs,
same result) and that each hard signal and gap kind actually fires.
"""

from __future__ import annotations

from datetime import date

from tprm_ddq.domain.contract_diff import diff_contract
from tprm_ddq.domain.evidence_ledger import EvidenceLedger
from tprm_ddq.domain.financials import FinancialPolicy, assess_financials
from tprm_ddq.domain.gap_engine import analyse_gaps
from tprm_ddq.domain.kernel import Citation, Severity
from tprm_ddq.domain.scoring_engine import ScoringPolicy, score_vendor
from tprm_ddq.domain.tprm_models import (
    CanonicalControl,
    ComplianceRequirement,
    ContractCommitment,
    ControlEffectiveness,
    DataClassification,
    EvidenceItem,
    EvidenceKind,
    FinancialFigures,
    GapKind,
    MediaCategory,
    MediaFinding,
    Substitutability,
    VendorProfile,
)

_AS_OF = date(2026, 1, 1)


def _cite(name: str) -> Citation:
    return Citation(source_id=name, title=name, snippet=name)


def _item(control: CanonicalControl, eff: ControlEffectiveness, **kw: object) -> EvidenceItem:
    return EvidenceItem(
        control=control,
        kind=EvidenceKind.SOC2,
        effectiveness=eff,
        as_of=date(2025, 6, 1),
        citation=_cite(control.value),
        **kw,  # type: ignore[arg-type]
    )


def _profile(**kw: object) -> VendorProfile:
    base: dict[str, object] = {
        "name": "Vendor (FICTIONAL)",
        "service_criticality": Severity.HIGH,
        "data_classification": DataClassification.RESTRICTED,
        "jurisdiction": "SG",
        "substitutability": Substitutability.SPECIALISED,
    }
    base.update(kw)
    return VendorProfile(**base)  # type: ignore[arg-type]


def test_scoring_is_deterministic_and_credits_effective_controls() -> None:
    profile = _profile()
    strong = EvidenceLedger(
        items=tuple(
            _item(c, ControlEffectiveness.EFFECTIVE) for c in ScoringPolicy().credited_controls
        )
    )
    first = score_vendor(profile, strong, (), None, as_of=_AS_OF)
    second = score_vendor(profile, strong, (), None, as_of=_AS_OF)
    assert first == second, "same inputs must produce the same score"
    # Restricted-data critical vendor with every control effective nets to a low residual.
    assert first.inherent_band == Severity.MEDIUM
    assert first.residual_band == Severity.LOW


def test_sanctions_media_forces_critical_residual() -> None:
    profile = _profile()
    ledger = EvidenceLedger(
        items=tuple(
            _item(c, ControlEffectiveness.EFFECTIVE) for c in ScoringPolicy().credited_controls
        )
    )
    media = (
        MediaFinding(
            subject=profile.name,
            category=MediaCategory.SANCTIONS,
            severity=Severity.CRITICAL,
            headline="watchlist (FICTIONAL)",
            citation=_cite("media"),
        ),
    )
    result = score_vendor(profile, ledger, media, None, as_of=_AS_OF)
    assert result.residual_band == Severity.CRITICAL
    assert "sanctions-category adverse media" in result.hard_signals


def test_expired_certificate_raises_the_band() -> None:
    profile = _profile()
    item = _item(CanonicalControl.ENCRYPTION, ControlEffectiveness.EFFECTIVE, expired=True)
    ledger = EvidenceLedger(items=(item,))
    result = score_vendor(profile, ledger, (), None, as_of=_AS_OF)
    assert "expired certification" in result.hard_signals


def test_financials_are_computed_not_narrated() -> None:
    healthy = FinancialFigures(
        current_assets=2_000_000,
        current_liabilities=1_000_000,
        total_debt=500_000,
        total_equity=2_000_000,
        going_concern_flag=False,
        citation=_cite("fin"),
    )
    status = assess_financials(healthy)
    assert status.current_ratio == 2.0
    assert status.liquidity == Severity.LOW
    assert status.going_concern is True

    distressed = FinancialFigures(
        current_assets=500_000,
        current_liabilities=1_000_000,
        total_debt=6_000_000,
        total_equity=1_000_000,
        going_concern_flag=True,
        citation=_cite("fin"),
    )
    bad = assess_financials(distressed, policy=FinancialPolicy())
    assert bad.liquidity == Severity.CRITICAL
    assert bad.leverage == Severity.CRITICAL
    assert bad.going_concern is False


def test_contract_diff_flags_a_residency_contradiction() -> None:
    ledger = EvidenceLedger(
        items=(_item(CanonicalControl.DATA_GOVERNANCE, ControlEffectiveness.INEFFECTIVE),)
    )
    commitments = (
        ContractCommitment(
            control=CanonicalControl.DATA_GOVERNANCE,
            term="data residency in-region",
            present=True,
            citation=_cite("clause"),
        ),
    )
    mismatches = diff_contract(commitments, ledger)
    assert len(mismatches) == 1
    assert mismatches[0].control == CanonicalControl.DATA_GOVERNANCE


def test_gap_engine_ranks_and_grounds_gaps() -> None:
    ledger = EvidenceLedger(
        items=(_item(CanonicalControl.ACCESS_CONTROL, ControlEffectiveness.INEFFECTIVE),)
    )
    requirements = {
        CanonicalControl.ACCESS_CONTROL: ComplianceRequirement(
            control=CanonicalControl.ACCESS_CONTROL,
            rule_ref="CPS 231 para 40 (FICTIONAL)",
            text="restrict access",
            citation=_cite("rsk1"),
        )
    }
    gaps = analyse_gaps(ledger, (), (), requirements, as_of=_AS_OF)
    kinds = {gap.kind for gap in gaps}
    assert GapKind.WEAK_CONTROL in kinds
    assert GapKind.MISSING_EVIDENCE in kinds
    weak = next(g for g in gaps if g.kind == GapKind.WEAK_CONTROL)
    assert weak.rule_ref == "CPS 231 para 40 (FICTIONAL)"
    # Ranked most severe first.
    from tprm_ddq.domain.tprm_models import SEVERITY_RANK

    ranks = [SEVERITY_RANK[g.severity] for g in gaps]
    assert ranks == sorted(ranks, reverse=True)
