"""Control-taxonomy packs as DATA: SOC 2 TSC, ISO 27001 Annex A and SIG/CAIQ to canonical.

The engine owns the mapping from each framework's own control identifiers to the one canonical
control set in :class:`~.tprm_models.CanonicalControl`, so the evidence ledger is keyed by a
control the scoring and gap engines understand regardless of which report an observation came
from. These are frozen module tables, not model output: a framework identifier the pack does
not know maps to nothing and is surfaced as an unmapped-evidence gap rather than guessed.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .tprm_models import CanonicalControl

# SOC 2 Trust Services Criteria (a representative subset) -> canonical control.
_SOC2_TSC: dict[str, CanonicalControl] = {
    "CC6.1": CanonicalControl.ACCESS_CONTROL,
    "CC6.6": CanonicalControl.ENCRYPTION,
    "CC7.2": CanonicalControl.LOGGING_MONITORING,
    "CC7.4": CanonicalControl.INCIDENT_RESPONSE,
    "CC8.1": CanonicalControl.CHANGE_MANAGEMENT,
    "CC9.2": CanonicalControl.VENDOR_MANAGEMENT,
    "A1.2": CanonicalControl.BUSINESS_CONTINUITY,
    "C1.1": CanonicalControl.DATA_GOVERNANCE,
}

# ISO 27001:2022 Annex A (a representative subset) -> canonical control.
_ISO_ANNEX_A: dict[str, CanonicalControl] = {
    "A.5.15": CanonicalControl.ACCESS_CONTROL,
    "A.8.24": CanonicalControl.ENCRYPTION,
    "A.5.24": CanonicalControl.INCIDENT_RESPONSE,
    "A.5.29": CanonicalControl.BUSINESS_CONTINUITY,
    "A.8.32": CanonicalControl.CHANGE_MANAGEMENT,
    "A.5.19": CanonicalControl.VENDOR_MANAGEMENT,
    "A.5.34": CanonicalControl.DATA_GOVERNANCE,
    "A.8.15": CanonicalControl.LOGGING_MONITORING,
    "A.6.1": CanonicalControl.HR_SECURITY,
    "A.5.1": CanonicalControl.RISK_MANAGEMENT,
}

# SIG/CAIQ-style domains -> canonical control.
_SIG_CAIQ: dict[str, CanonicalControl] = {
    "IAM": CanonicalControl.ACCESS_CONTROL,
    "CEK": CanonicalControl.ENCRYPTION,
    "SEF": CanonicalControl.INCIDENT_RESPONSE,
    "BCR": CanonicalControl.BUSINESS_CONTINUITY,
    "CCC": CanonicalControl.CHANGE_MANAGEMENT,
    "STA": CanonicalControl.VENDOR_MANAGEMENT,
    "DSP": CanonicalControl.DATA_GOVERNANCE,
    "LOG": CanonicalControl.LOGGING_MONITORING,
    "HRS": CanonicalControl.HR_SECURITY,
    "GRC": CanonicalControl.RISK_MANAGEMENT,
}

#: framework name -> (its identifier -> canonical control). Read-only views so no caller mutates
#: a shared table.
FRAMEWORK_PACKS: Mapping[str, Mapping[str, CanonicalControl]] = MappingProxyType(
    {
        "soc2": MappingProxyType(dict(_SOC2_TSC)),
        "iso27001": MappingProxyType(dict(_ISO_ANNEX_A)),
        "sig_caiq": MappingProxyType(dict(_SIG_CAIQ)),
    }
)

#: The controls a material outsourcing arrangement is expected to evidence. A canonical control
#: with no evidence item is a mandatory-evidence gap (``gap_engine``). Adopter-owned policy.
MANDATORY_CONTROLS: tuple[CanonicalControl, ...] = (
    CanonicalControl.ACCESS_CONTROL,
    CanonicalControl.ENCRYPTION,
    CanonicalControl.INCIDENT_RESPONSE,
    CanonicalControl.BUSINESS_CONTINUITY,
    CanonicalControl.DATA_GOVERNANCE,
    CanonicalControl.LOGGING_MONITORING,
)


def map_control(framework: str, identifier: str) -> CanonicalControl | None:
    """Map one framework identifier to a canonical control, or ``None`` if the pack lacks it.

    ``None`` is deliberate: an unknown identifier is surfaced as an unmapped-evidence gap by the
    caller, never coerced into a nearby control. The lookup is case-sensitive on the framework
    name and exact on the identifier.
    """
    pack = FRAMEWORK_PACKS.get(framework)
    if pack is None:
        return None
    return pack.get(identifier)
