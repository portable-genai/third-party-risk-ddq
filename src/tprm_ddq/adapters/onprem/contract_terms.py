"""On-prem ContractTermsPort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import ContractCommitment


class OnPremContractTermsAdapter:
    """Satisfies the port but refuses: the client binds its own contract register."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def commitments(self, vendor: str, *, tenant: str = "") -> tuple[ContractCommitment, ...]:
        raise NotImplementedError(
            "on-prem contract-terms is a portability placeholder: bind the client's own contract "
            "obligation register (see docs/onprem-migration.md)"
        )
