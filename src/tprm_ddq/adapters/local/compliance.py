"""Local CompliancePort: a fixture outsourcing-rule KB (compliance-advisory stand-in, SDK-free).

Deterministic requirement text and a citation per canonical control. The parameter shapes echo APRA
CPS 231 / MAS & HKMA outsourcing expectations, kept obviously synthetic. third-party-risk-ddq never
invents regulatory text: a control with no entry here returns nothing, and the gap engine records
the gap with an explicit "no rule text available" reference rather than a guess.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...config import Settings
from ...domain.kernel import Citation
from ...domain.tprm_models import CanonicalControl, ComplianceRequirement

_KB: dict[CanonicalControl, tuple[str, str]] = {
    CanonicalControl.ACCESS_CONTROL: (
        "CPS 231 para 40 (FICTIONAL ref)",
        "the outsourcing arrangement must restrict access to authorised personnel",
    ),
    CanonicalControl.ENCRYPTION: (
        "CPS 234 para 22 (FICTIONAL ref)",
        "information assets must be protected in transit and at rest",
    ),
    CanonicalControl.INCIDENT_RESPONSE: (
        "CPS 234 para 35 (FICTIONAL ref)",
        "the provider must notify material incidents without undue delay",
    ),
    CanonicalControl.BUSINESS_CONTINUITY: (
        "CPS 230 para 44 (FICTIONAL ref)",
        "the provider must maintain and test business continuity arrangements",
    ),
    CanonicalControl.DATA_GOVERNANCE: (
        "CPS 231 para 47 (FICTIONAL ref)",
        "data residency and sovereignty commitments must be enforceable",
    ),
    CanonicalControl.LOGGING_MONITORING: (
        "CPS 234 para 28 (FICTIONAL ref)",
        "security monitoring and logging must be maintained and reviewed",
    ),
}


class LocalComplianceAdapter:
    """Return fixture outsourcing-rule expectations for the requested controls."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def requirements(
        self, controls: tuple[CanonicalControl, ...], *, actor: str
    ) -> Mapping[CanonicalControl, ComplianceRequirement]:
        out: dict[CanonicalControl, ComplianceRequirement] = {}
        for control in controls:
            entry = _KB.get(control)
            if entry is None:
                continue
            rule_ref, text = entry
            out[control] = ComplianceRequirement(
                control=control,
                rule_ref=rule_ref,
                text=text,
                citation=Citation(
                    source_id=f"rsk1:{control.value}",
                    title=rule_ref,
                    snippet=text[:80],
                ),
            )
        return out
