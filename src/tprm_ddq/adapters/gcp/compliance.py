"""GCP CompliancePort: platform A2A client to compliance-advisory's regulatory KB (lazy import)."""

from __future__ import annotations

from collections.abc import Mapping

from ...config import Settings
from ...domain.tprm_models import CanonicalControl, ComplianceRequirement


class CloudComplianceAdapter:
    """Fetch outsourcing-rule expectations from compliance-advisory over A2A. Refuses when
    unconfigured.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def requirements(  # pragma: no cover - live platform
        self, controls: tuple[CanonicalControl, ...], *, actor: str
    ) -> Mapping[CanonicalControl, ComplianceRequirement]:
        import urllib.request  # noqa: F401

        raise RuntimeError(
            "compliance-advisory compliance A2A endpoint is not configured; set the regulatory KB "
            "URL before "
            "selecting the gcp profile for compliance"
        )
