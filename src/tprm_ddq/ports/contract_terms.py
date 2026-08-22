"""ContractTermsPort: the vendor's contractual commitments from Rgc12 (slice 3).

Returns the commitments (audit and step-in rights, sub-outsourcing, data residency, exit
assistance, SLAs), each keyed to the canonical control it evidences, so ``contract_diff`` can
diff them against the evidence ledger deterministically. The primary adapter is a platform A2A
client to Rgc12's contract-obligation register; ``local`` is a fixture register; ``onprem`` fails
fast. Rgc12 is unshipped in this workspace, so the fixture adapter freezes the contract shape
and a contract test pins it (the standing soft-edge rule).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.tprm_models import ContractCommitment


@runtime_checkable
class ContractTermsPort(Protocol):
    def commitments(self, vendor: str, *, tenant: str = "") -> tuple[ContractCommitment, ...]:
        """Return the vendor's contractual commitments, keyed to canonical controls."""
        ...
