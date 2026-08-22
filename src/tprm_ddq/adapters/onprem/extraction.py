"""On-prem DocumentExtractionPort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import DocumentRef, ExtractedDocument


class OnPremExtractionAdapter:
    """Satisfies the port but refuses: the client binds its own document extraction."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def extract(self, document: DocumentRef) -> ExtractedDocument:
        raise NotImplementedError(
            "on-prem extraction is a portability placeholder: bind the client's own document "
            "extraction service (see docs/onprem-migration.md)"
        )
