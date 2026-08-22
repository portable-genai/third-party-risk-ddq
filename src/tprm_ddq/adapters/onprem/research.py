"""On-prem AdverseMediaPort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import MediaFinding


class OnPremAdverseMediaAdapter:
    """Satisfies the port but refuses: the client binds its own adverse-media source."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def search(self, subject_name: str) -> tuple[MediaFinding, ...]:
        raise NotImplementedError(
            "on-prem adverse-media is a portability placeholder: bind the client's own screening "
            "feed (see docs/onprem-migration.md)"
        )
