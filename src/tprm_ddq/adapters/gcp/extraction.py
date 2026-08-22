"""GCP DocumentExtractionPort: Document AI (SDK imports stay lazy)."""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import DocumentRef, ExtractedDocument


class CloudExtractionAdapter:
    """Extract evidence documents with Document AI. Import is lazy for the offline profiles."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def extract(self, document: DocumentRef) -> ExtractedDocument:  # pragma: no cover - live GCP
        from google.cloud import documentai  # noqa: F401

        raise RuntimeError(
            "GCP Document AI extraction is not configured in this deployment; bind the "
            "processor id and region before selecting the gcp profile for extraction"
        )
