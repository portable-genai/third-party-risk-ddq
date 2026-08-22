"""Domain errors that carry an HTTP-shaped intent without importing a web framework.

``CrossTenantError`` is the authorisation refusal the register read raises when a caller asks
for a tenant other than the verified principal's. It is a 403 (authorised-against and denied),
never a 404 (which would leak whether the row exists): the API maps it to 403, and the domain is
where the decision lives so every surface inherits it.
"""

from __future__ import annotations


class CrossTenantError(PermissionError):
    """A caller tried to reach data outside the verified principal's tenant. Maps to HTTP 403."""

    status_code = 403

    def __init__(self, principal_tenant: str, requested_tenant: str) -> None:
        self.principal_tenant = principal_tenant
        self.requested_tenant = requested_tenant
        super().__init__(
            "cross-tenant access denied: the verified principal is not authorised for the "
            "requested tenant"
        )
