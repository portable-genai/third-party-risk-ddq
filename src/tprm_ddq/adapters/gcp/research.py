"""GCP AdverseMediaPort: Grounding with Google Search in an isolated sub-agent (lazy import)."""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import MediaFinding


class CloudAdverseMediaAdapter:
    """Search adverse media via a grounded sub-agent. Web egress stays in this one place."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def search(self, subject_name: str) -> tuple[MediaFinding, ...]:  # pragma: no cover - live GCP
        from google import genai  # noqa: F401

        raise RuntimeError(
            "grounded adverse-media search is not configured; bind the grounding sub-agent "
            "before selecting the gcp profile for research"
        )
