"""Local GenerationPort: a DETERMINISTIC rule-based stub (the determinism proof).

This is the stub the house determinism invariant names: with generation bound here, every
consequential number is identical, because this adapter produces only prose and schema-valid
claims, never a band or a score. It normalises DDQ answers with a keyword rule, drafts one
follow-up per gap from the gap's own fields, and assembles the memo from the engine's outputs.
No model, no network; the ``gcp`` adapter swaps in Gemini and validates its JSON the same way.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.tprm_models import (
    ControlEffectiveness,
    DDQClaim,
    Gap,
    LlmDraft,
    RawDDQAnswer,
)

# Keyword rules the stub uses to read a self-attested effectiveness from a DDQ answer. The
# reading is advisory only: it never enters the score (the ledger's tested evidence does).
_POSITIVE = ("enforce", "mandatory", "encrypted", "tested", "certified", "all ")
_NEGATIVE = ("no ", "not ", "planned", "roadmap", "manual", "ad hoc", "none")


class LocalGenerationAdapter:
    """Deterministic narration: prose and schema-valid claims, never a number."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def normalise_ddq(self, answers: tuple[RawDDQAnswer, ...]) -> tuple[DDQClaim, ...]:
        claims: list[DDQClaim] = []
        for answer in answers:
            control = answer.control
            if control is None:
                # Unparseable domain: dropped here, surfaced as an unanswered-domain gap upstream.
                continue
            claims.append(
                DDQClaim(
                    control=control,
                    effectiveness=self._read(answer.answer_text),
                    answer_text=answer.answer_text,
                    citation=answer.citation,
                )
            )
        return tuple(claims)

    @staticmethod
    def _read(text: str) -> ControlEffectiveness:
        lowered = text.lower()
        if any(term in lowered for term in _NEGATIVE):
            return ControlEffectiveness.INEFFECTIVE
        if any(term in lowered for term in _POSITIVE):
            return ControlEffectiveness.EFFECTIVE
        return ControlEffectiveness.PARTIAL

    def draft_followups(self, gaps: tuple[Gap, ...]) -> tuple[LlmDraft, ...]:
        drafts: list[LlmDraft] = []
        for gap in gaps:
            question = (
                f"Regarding {gap.control.value}: please provide evidence addressing "
                f"'{gap.description}' (ref {gap.rule_ref})."
            )
            drafts.append(LlmDraft(text=question, grounded_gap_ids=(gap.gap_id,)))
        return tuple(drafts)

    def draft_memo(self, vendor: str, residual_band: str, grounded_gap_ids: tuple[str, ...]) -> str:
        gap_line = ", ".join(grounded_gap_ids) if grounded_gap_ids else "no open gaps"
        return (
            f"Risk-acceptance memo for {vendor}. The deterministic engine assessed a residual "
            f"risk band of {residual_band}. Open items requiring disposition: {gap_line}. "
            "This memo is a maker proposal and requires human review before any acceptance."
        )
