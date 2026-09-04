"""CompliancePort: the outsourcing-rule expectations from compliance-advisory (slice 6).

Each gap maps to the outsourcing-rule expectation it offends; this port fetches that rule text and
its citation from compliance-advisory's regulatory KB so third-party-risk-ddq never invents
regulatory text (the grounding rule the exit-and-portability planner's ``concentration_service``
records). The primary adapter is a platform A2A client to compliance-advisory (mirroring the
exit-and-portability planner's ``remote_compliance``); ``local`` is a fixture KB; ``onprem`` fails
fast.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from ..domain.tprm_models import CanonicalControl, ComplianceRequirement


@runtime_checkable
class CompliancePort(Protocol):
    def requirements(
        self, controls: tuple[CanonicalControl, ...], *, actor: str
    ) -> Mapping[CanonicalControl, ComplianceRequirement]:
        """Fetch the outsourcing-rule expectation (text + citation) for each control."""
        ...
