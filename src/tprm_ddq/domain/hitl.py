"""Human-in-the-loop policy for the risk-acceptance memo (rule R8 / P-06).

A risk-acceptance decision is consequential and board-and-regulator-facing, so the memo is
ALWAYS human: ``requires_review`` is unconditionally True (mirroring Rsk5's ``ExitReviewPolicy``).
``escalates`` marks the memo for senior / risk-committee sign-off when the residual band is at or
above the escalation floor or any hard signal fired. Pure decision logic; no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass

from .kernel import Severity
from .tprm_models import SEVERITY_RANK

_ESCALATION_FLOOR: Severity = Severity.HIGH


@dataclass(frozen=True, slots=True)
class MemoReviewPolicy:
    """Maker-checker gate for the risk-acceptance memo. Pure; no side effects."""

    escalation_floor: Severity = _ESCALATION_FLOOR

    def requires_review(self, residual_band: Severity, hard_signals: tuple[str, ...]) -> bool:
        """Whether the memo needs human review. Always True: a risk acceptance is consequential."""
        _ = (residual_band, hard_signals)
        return True

    def escalates(self, residual_band: Severity, hard_signals: tuple[str, ...]) -> bool:
        """Whether the memo escalates to senior review (high residual or any hard signal)."""
        if hard_signals:
            return True
        return SEVERITY_RANK[residual_band] >= SEVERITY_RANK[self.escalation_floor]
