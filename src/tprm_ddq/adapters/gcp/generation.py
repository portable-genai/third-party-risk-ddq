"""GCP GenerationPort: Gemini on the Agent Platform (SDK imports stay lazy).

The model NARRATES only; its JSON is schema-validated and DISCARDED on failure, never trusted.
The import lives inside the method so the offline profiles import this module with no SDK.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import DDQClaim, Gap, LlmDraft, RawDDQAnswer


class CloudGenerationAdapter:
    """Narrate with Gemini. Refuses rather than returning unvalidated output when unconfigured."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def normalise_ddq(  # pragma: no cover - live GCP
        self, answers: tuple[RawDDQAnswer, ...]
    ) -> tuple[DDQClaim, ...]:
        from google import genai  # noqa: F401

        raise RuntimeError("Gemini generation is not configured for the gcp profile")

    def draft_followups(  # pragma: no cover - live GCP
        self, gaps: tuple[Gap, ...]
    ) -> tuple[LlmDraft, ...]:
        from google import genai  # noqa: F401

        raise RuntimeError("Gemini generation is not configured for the gcp profile")

    def draft_memo(  # pragma: no cover - live GCP
        self, vendor: str, residual_band: str, grounded_gap_ids: tuple[str, ...]
    ) -> str:
        from google import genai  # noqa: F401

        raise RuntimeError("Gemini generation is not configured for the gcp profile")
