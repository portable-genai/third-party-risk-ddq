"""On-prem RegisterStorePort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import RegisterEntry


class OnPremRegisterStoreAdapter:
    """Satisfies the port but refuses: the client binds its own register store."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def upsert(self, entry: RegisterEntry) -> str:
        raise NotImplementedError(
            "on-prem register store is a portability placeholder: bind the client's own store "
            "(see docs/onprem-migration.md)"
        )

    def get(self, vendor: str, *, tenant: str) -> RegisterEntry | None:
        raise NotImplementedError(
            "on-prem register store is a portability placeholder: bind the client's own store "
            "(see docs/onprem-migration.md)"
        )

    def list_for_tenant(self, tenant: str) -> tuple[RegisterEntry, ...]:
        raise NotImplementedError(
            "on-prem register store is a portability placeholder: bind the client's own store "
            "(see docs/onprem-migration.md)"
        )
