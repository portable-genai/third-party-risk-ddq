"""Register access with tenant authorisation (slice 7).

The register store is tenant-scoped, but the AUTHORISATION lives here in the domain so every
surface inherits it: a read is authorised against the VERIFIED principal's tenant, and a request
for a different tenant is a 403 (``CrossTenantError``), never a silent 404. The principal's
tenant is passed in from the resolved identity; a caller never asserts it off the artifact.
"""

from __future__ import annotations

from dataclasses import replace

from ..ports.register_store import RegisterStorePort
from .errors import CrossTenantError
from .tprm_models import RegisterEntry


class RegisterService:
    """Authorise register reads against the verified principal's tenant, then delegate."""

    def __init__(self, store: RegisterStorePort) -> None:
        self._store = store

    def get(
        self, vendor: str, *, requested_tenant: str, principal_tenant: str
    ) -> RegisterEntry | None:
        """Return the vendor's entry within the principal's tenant, or refuse cross-tenant.

        A request whose ``requested_tenant`` differs from ``principal_tenant`` is denied with a
        403 rather than answered, so the caller cannot probe another tenant's register by naming
        it. Within the authorised tenant a missing row is a normal ``None``.
        """
        if requested_tenant and requested_tenant != principal_tenant:
            raise CrossTenantError(principal_tenant, requested_tenant)
        return self._store.get(vendor, tenant=principal_tenant)

    def upsert(self, entry: RegisterEntry, *, principal_tenant: str) -> str:
        """Persist an entry, forcing the row's tenant to the verified principal's."""
        if entry.tenant and entry.tenant != principal_tenant:
            raise CrossTenantError(principal_tenant, entry.tenant)
        return self._store.upsert(replace(entry, tenant=principal_tenant))
