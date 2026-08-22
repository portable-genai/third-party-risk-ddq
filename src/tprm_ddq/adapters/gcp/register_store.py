"""GCP RegisterStorePort: AlloyDB-backed register (SDK imports stay lazy)."""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import RegisterEntry


class CloudRegisterStoreAdapter:
    """Persist the outsourcing register to AlloyDB. Import is lazy for the offline profiles."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def upsert(self, entry: RegisterEntry) -> str:  # pragma: no cover - live GCP
        from google.cloud.alloydb.connector import Connector  # noqa: F401

        raise RuntimeError("AlloyDB register store is not configured for the gcp profile")

    def get(  # pragma: no cover - live GCP
        self, vendor: str, *, tenant: str
    ) -> RegisterEntry | None:
        from google.cloud.alloydb.connector import Connector  # noqa: F401

        raise RuntimeError("AlloyDB register store is not configured for the gcp profile")

    def list_for_tenant(  # pragma: no cover - live GCP
        self, tenant: str
    ) -> tuple[RegisterEntry, ...]:
        from google.cloud.alloydb.connector import Connector  # noqa: F401

        raise RuntimeError("AlloyDB register store is not configured for the gcp profile")
