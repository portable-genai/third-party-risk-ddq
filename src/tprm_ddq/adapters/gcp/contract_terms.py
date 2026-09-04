"""GCP ContractTermsPort: platform A2A client to contract-obligation-extraction (SDK/import stays
lazy).
"""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import ContractCommitment


class CloudContractTermsAdapter:
    """Fetch contractual commitments from contract-obligation-extraction over A2A. Refuses when
    unconfigured.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def commitments(  # pragma: no cover - live platform
        self, vendor: str, *, tenant: str = ""
    ) -> tuple[ContractCommitment, ...]:
        import urllib.request  # noqa: F401

        raise RuntimeError(
            "contract-obligation-extraction contract-terms A2A endpoint is not configured; set the "
            "contract register URL "
            "before selecting the gcp profile for contract_terms"
        )
