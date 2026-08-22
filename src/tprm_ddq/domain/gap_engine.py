"""Cited gap analysis (slice 6): a pure function of the evidence ledger.

Same inputs, same ranked gaps, no clock beyond ``as_of`` (Doc1's ``gap_analysis`` shape). It
finds missing mandatory evidence, stale reports, contract-versus-evidence mismatches, unanswered
DDQ domains and tested-weak controls. Each gap maps to the outsourcing-rule expectation it
offends through the ``ComplianceRequirement`` the compliance port supplied, so the engine never
invents regulatory text: a control with no requirement fetched still yields a gap, cited to the
evidence, but with an explicit "no rule text available" reference rather than a guessed one.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from .control_taxonomy import MANDATORY_CONTROLS
from .evidence_ledger import EvidenceLedger
from .kernel import Citation, Severity
from .tprm_models import (
    EFFECTIVENESS_RANK,
    SEVERITY_RANK,
    CanonicalControl,
    ComplianceRequirement,
    ContractMismatch,
    ControlEffectiveness,
    DDQClaim,
    Gap,
    GapKind,
)

#: Controls whose absence is a HIGH gap rather than MEDIUM (data-protection critical).
_HIGH_SEVERITY_CONTROLS: frozenset[CanonicalControl] = frozenset(
    {
        CanonicalControl.ENCRYPTION,
        CanonicalControl.INCIDENT_RESPONSE,
        CanonicalControl.DATA_GOVERNANCE,
    }
)

#: Evidence older than this many days (relative to ``as_of``) is stale. Adopter-owned policy.
STALE_AFTER_DAYS = 400

_NO_RULE = "no outsourcing-rule text available (compliance KB returned none)"


def _control_severity(control: CanonicalControl, floor: Severity) -> Severity:
    band = Severity.HIGH if control in _HIGH_SEVERITY_CONTROLS else floor
    return band


def _requirement(
    control: CanonicalControl, requirements: Mapping[CanonicalControl, ComplianceRequirement]
) -> tuple[str, Citation]:
    req = requirements.get(control)
    if req is None:
        return _NO_RULE, Citation(source_id="compliance:none", title="No rule text")
    return req.rule_ref, req.citation


def analyse_gaps(
    ledger: EvidenceLedger,
    ddq_claims: tuple[DDQClaim, ...],
    mismatches: tuple[ContractMismatch, ...],
    requirements: Mapping[CanonicalControl, ComplianceRequirement],
    *,
    as_of: date,
) -> tuple[Gap, ...]:
    """Return the ranked gaps. Deterministic: same inputs, same order."""
    gaps: list[Gap] = []

    # Missing mandatory evidence.
    for control in ledger.missing_mandatory():
        rule_ref, citation = _requirement(control, requirements)
        gaps.append(
            Gap(
                gap_id=f"gap-missing-{control.value}",
                kind=GapKind.MISSING_EVIDENCE,
                control=control,
                severity=_control_severity(control, Severity.MEDIUM),
                description=f"no evidence for mandatory control {control.value}",
                rule_ref=rule_ref,
                citation=citation,
            )
        )

    # Unanswered DDQ domains: mandatory controls with no normalised DDQ claim.
    answered = frozenset(claim.control for claim in ddq_claims)
    for control in MANDATORY_CONTROLS:
        if control in answered:
            continue
        rule_ref, citation = _requirement(control, requirements)
        gaps.append(
            Gap(
                gap_id=f"gap-unanswered-{control.value}",
                kind=GapKind.UNANSWERED_DOMAIN,
                control=control,
                severity=Severity.MEDIUM,
                description=f"DDQ leaves {control.value} unanswered",
                rule_ref=rule_ref,
                citation=citation,
            )
        )

    # Tested-weak controls: evidenced but at or below INEFFECTIVE.
    for control in ledger.controls_present():
        best = ledger.best_effectiveness(control)
        if EFFECTIVENESS_RANK[best] <= EFFECTIVENESS_RANK[ControlEffectiveness.INEFFECTIVE]:
            rule_ref, citation = _requirement(control, requirements)
            items = ledger.for_control(control)
            gaps.append(
                Gap(
                    gap_id=f"gap-weak-{control.value}",
                    kind=GapKind.WEAK_CONTROL,
                    control=control,
                    severity=_control_severity(control, Severity.MEDIUM),
                    description=f"{control.value} evidenced but tests {best.value}",
                    rule_ref=rule_ref,
                    citation=items[0].citation if items else citation,
                )
            )

    # Stale evidence.
    for item in ledger.stale_items(as_of, max_age_days=STALE_AFTER_DAYS):
        rule_ref, citation = _requirement(item.control, requirements)
        gaps.append(
            Gap(
                gap_id=f"gap-stale-{item.control.value}-{item.as_of.isoformat()}",
                kind=GapKind.STALE_EVIDENCE,
                control=item.control,
                severity=Severity.MEDIUM,
                description=(
                    f"{item.kind.value} for {item.control.value} dated {item.as_of.isoformat()} "
                    "is stale"
                ),
                rule_ref=rule_ref,
                citation=item.citation,
            )
        )

    # Contract-versus-evidence mismatches.
    for mismatch in mismatches:
        rule_ref, citation = _requirement(mismatch.control, requirements)
        gaps.append(
            Gap(
                gap_id=f"gap-contract-{mismatch.control.value}",
                kind=GapKind.CONTRACT_MISMATCH,
                control=mismatch.control,
                severity=Severity.HIGH,
                description=mismatch.description,
                rule_ref=rule_ref,
                citation=mismatch.clause_citation,
            )
        )

    gaps.sort(key=lambda g: (-SEVERITY_RANK[g.severity], g.control.value, g.kind.value))
    return tuple(gaps)
