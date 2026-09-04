"""Local ContractTermsPort: a fixture contract register (contract-obligation-extraction stand-in,
SDK-free).

contract-obligation-extraction is unshipped in this workspace, so this fixture freezes the
contract-commitment shape and a contract test pins it. Deterministic commitments keyed by vendor and
canonical control. Obviously synthetic parties only.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.kernel import Citation
from ...domain.tprm_models import CanonicalControl, ContractCommitment


def _clause(vendor: str, control: CanonicalControl, term: str, present: bool) -> ContractCommitment:
    return ContractCommitment(
        control=control,
        term=term,
        present=present,
        citation=Citation(
            source_id=f"contract:{vendor}:{control.value}",
            title=f"MSA clause for {control.value}",
            snippet=term,
        ),
    )


_REGISTER: dict[str, tuple[ContractCommitment, ...]] = {
    "Nimbus Cloud Services (FICTIONAL)": (
        _clause("nimbus", CanonicalControl.DATA_GOVERNANCE, "data residency in-region", True),
        _clause("nimbus", CanonicalControl.INCIDENT_RESPONSE, "24h breach notification", True),
        _clause("nimbus", CanonicalControl.VENDOR_MANAGEMENT, "audit and step-in rights", True),
    ),
    "Cornerstone Payments Inc (FICTIONAL)": (
        # Contract commits to residency, but the DDQ/evidence contradicts it: the golden mismatch.
        _clause("cornerstone", CanonicalControl.DATA_GOVERNANCE, "data residency in-region", True),
        _clause("cornerstone", CanonicalControl.INCIDENT_RESPONSE, "breach notification", False),
    ),
}


class LocalContractTermsAdapter:
    """Return fixture contractual commitments for a vendor (the frozen
    contract-obligation-extraction contract).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def commitments(self, vendor: str, *, tenant: str = "") -> tuple[ContractCommitment, ...]:
        return _REGISTER.get(vendor, ())
