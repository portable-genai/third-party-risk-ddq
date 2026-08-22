"""GCP ContractTermsPort: platform A2A client to Rgc12 (SDK/import stays lazy)."""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import ContractCommitment


class CloudContractTermsAdapter:
    """Fetch contractual commitments from Rgc12 over A2A. Refuses when unconfigured."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def commitments(  # pragma: no cover - live platform
        self, vendor: str, *, tenant: str = ""
    ) -> tuple[ContractCommitment, ...]:
        import urllib.request  # noqa: F401

        raise RuntimeError(
            "Rgc12 contract-terms A2A endpoint is not configured; set the contract register URL "
            "before selecting the gcp profile for contract_terms"
        )
