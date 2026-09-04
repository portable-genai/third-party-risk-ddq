"""RegisterStorePort: the Outsourcing and Material-Arrangements Register (slice 7).

A tenant-scoped store for the register operational-resilience-mapping consumes over A2A. ``upsert``
and ``get`` authorise against the VERIFIED principal's tenant and return a cross-tenant read as a
denial, not a miss (403, not 404, is enforced in the domain caller). Materiality is flagged
deterministically from policy thresholds by the store, never asserted by a caller. Adapters: GCP
AlloyDB (lazy import), local SQLite/in-memory, onprem fail-fast.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.tprm_models import RegisterEntry


@runtime_checkable
class RegisterStorePort(Protocol):
    def upsert(self, entry: RegisterEntry) -> str:
        """Persist a register entry for its tenant and return its stable key."""
        ...

    def get(self, vendor: str, *, tenant: str) -> RegisterEntry | None:
        """Return the entry for ``vendor`` WITHIN ``tenant``, or ``None`` if absent for it.

        A row that exists under a DIFFERENT tenant must not be returned here: the tenant is part
        of the identity of the row, so a cross-tenant read is a miss for this tenant, and the
        API turns an explicit cross-tenant attempt into a 403 via the domain authorisation check.
        """
        ...

    def list_for_tenant(self, tenant: str) -> tuple[RegisterEntry, ...]:
        """Every register entry visible to ``tenant`` (deterministic order)."""
        ...
