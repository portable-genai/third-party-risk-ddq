"""Local RegisterStorePort: an in-memory tenant-scoped register (SDK-free stand-in for AlloyDB).

Rows are keyed by ``(tenant, vendor)``, so a read names its tenant and a row filed under another
tenant is simply not visible here; the domain authorisation check turns an explicit cross-tenant
attempt into a 403. Materiality is recomputed by the store from the residual band on every
upsert (policy, not a caller assertion).
"""

from __future__ import annotations

from dataclasses import replace

from ...config import Settings
from ...domain.kernel import Severity
from ...domain.tprm_models import SEVERITY_RANK, RegisterEntry

#: Residual band at or above which a vendor arrangement is material. Adopter-owned policy.
_MATERIAL_FLOOR: Severity = Severity.HIGH


def is_material(residual_band: Severity) -> bool:
    """Deterministic materiality from the residual band. Policy, not a caller assertion."""
    return SEVERITY_RANK[residual_band] >= SEVERITY_RANK[_MATERIAL_FLOOR]


class LocalRegisterStoreAdapter:
    """In-memory register keyed by tenant then vendor. Deterministic listing order."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._rows: dict[tuple[str, str], RegisterEntry] = {}

    def upsert(self, entry: RegisterEntry) -> str:
        stored = replace(entry, material=is_material(entry.residual_band))
        key = (stored.tenant, stored.vendor)
        self._rows[key] = stored
        return f"register:{stored.tenant}:{stored.vendor}"

    def get(self, vendor: str, *, tenant: str) -> RegisterEntry | None:
        return self._rows.get((tenant, vendor))

    def list_for_tenant(self, tenant: str) -> tuple[RegisterEntry, ...]:
        rows = [entry for (t, _), entry in self._rows.items() if t == tenant]
        return tuple(sorted(rows, key=lambda e: e.vendor))
