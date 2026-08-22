"""On-prem CompliancePort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from collections.abc import Mapping

from ...config import Settings
from ...domain.tprm_models import CanonicalControl, ComplianceRequirement


class OnPremComplianceAdapter:
    """Satisfies the port but refuses: the client binds its own regulatory KB."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def requirements(
        self, controls: tuple[CanonicalControl, ...], *, actor: str
    ) -> Mapping[CanonicalControl, ComplianceRequirement]:
        raise NotImplementedError(
            "on-prem compliance is a portability placeholder: bind the client's own outsourcing "
            "regulatory KB (see docs/onprem-migration.md)"
        )
