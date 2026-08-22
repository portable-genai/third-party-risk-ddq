"""On-prem GenerationPort: fail-fast portability placeholder (P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import DDQClaim, Gap, LlmDraft, RawDDQAnswer


class OnPremGenerationAdapter:
    """Satisfies the port but refuses: the client binds its own model runtime."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def normalise_ddq(self, answers: tuple[RawDDQAnswer, ...]) -> tuple[DDQClaim, ...]:
        raise NotImplementedError(
            "on-prem generation is a portability placeholder: bind the client's own model "
            "(see docs/onprem-migration.md)"
        )

    def draft_followups(self, gaps: tuple[Gap, ...]) -> tuple[LlmDraft, ...]:
        raise NotImplementedError(
            "on-prem generation is a portability placeholder: bind the client's own model "
            "(see docs/onprem-migration.md)"
        )

    def draft_memo(self, vendor: str, residual_band: str, grounded_gap_ids: tuple[str, ...]) -> str:
        raise NotImplementedError(
            "on-prem generation is a portability placeholder: bind the client's own model "
            "(see docs/onprem-migration.md)"
        )
