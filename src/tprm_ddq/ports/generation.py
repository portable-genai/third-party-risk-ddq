"""GenerationPort: the LLM used to NARRATE only (slices 2, 4, 6).

The model normalises free-text DDQ answers into schema-validated claims, drafts follow-up
question wording for engine-identified gaps and drafts the risk-acceptance memo prose. It never
produces a risk band, a score or a gap: those come from the deterministic engines, so with this
port stubbed by the ``local`` adapter every consequential number is identical. Every method is
schema-validated and discards model output on failure rather than trusting it.

Primary adapter: Gemini on the Agent Platform (lazy import), pinned to ``asia-southeast1``;
``local`` is a deterministic rule-based stub (the determinism proof); ``onprem`` fails fast.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.tprm_models import DDQClaim, Gap, LlmDraft, RawDDQAnswer


@runtime_checkable
class GenerationPort(Protocol):
    def normalise_ddq(self, answers: tuple[RawDDQAnswer, ...]) -> tuple[DDQClaim, ...]:
        """Normalise free-text DDQ answers into schema-valid claims; drop unparseable ones."""
        ...

    def draft_followups(self, gaps: tuple[Gap, ...]) -> tuple[LlmDraft, ...]:
        """Draft one follow-up question per gap, each tied to the gap id it addresses."""
        ...

    def draft_memo(self, vendor: str, residual_band: str, grounded_gap_ids: tuple[str, ...]) -> str:
        """Draft the risk-acceptance memo prose (no number the engine did not produce)."""
        ...
