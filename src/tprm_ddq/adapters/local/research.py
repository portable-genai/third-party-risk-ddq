"""Local AdverseMediaPort: a fictional, severity-ordered fixture corpus (SDK-free).

Deterministic findings keyed by subject name. Obviously synthetic: fictional parties and
``.example`` sources only. A subject not in the corpus returns no findings (a clean search),
which is a real answer, not a refusal.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.kernel import Citation, Severity
from ...domain.tprm_models import MediaCategory, MediaFinding

_CORPUS: dict[str, tuple[MediaFinding, ...]] = {
    "Meridian Offshore Data Ltd (FICTIONAL)": (
        MediaFinding(
            subject="Meridian Offshore Data Ltd (FICTIONAL)",
            category=MediaCategory.SANCTIONS,
            severity=Severity.CRITICAL,
            headline="Regulator adds parent group to a sanctions watchlist (FICTIONAL)",
            citation=Citation(
                source_id="media:meridian-1",
                title="Sanctions watchlist notice (FICTIONAL)",
                snippet="added to a consolidated watchlist",
            ),
        ),
    ),
    "Cornerstone Payments Inc (FICTIONAL)": (
        MediaFinding(
            subject="Cornerstone Payments Inc (FICTIONAL)",
            category=MediaCategory.DATA_BREACH,
            severity=Severity.HIGH,
            headline="Undisclosed breach exposed customer records (FICTIONAL)",
            citation=Citation(
                source_id="media:cornerstone-1",
                title="Breach report (FICTIONAL)",
                snippet="records exposed for several weeks",
            ),
        ),
        MediaFinding(
            subject="Cornerstone Payments Inc (FICTIONAL)",
            category=MediaCategory.LITIGATION,
            severity=Severity.MEDIUM,
            headline="Class action filed over the breach (FICTIONAL)",
            citation=Citation(
                source_id="media:cornerstone-2",
                title="Litigation notice (FICTIONAL)",
                snippet="class action filed",
            ),
        ),
    ),
}

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


class LocalAdverseMediaAdapter:
    """Return fictional adverse-media findings, most severe first, for a subject."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def search(self, subject_name: str) -> tuple[MediaFinding, ...]:
        findings = _CORPUS.get(subject_name, ())
        return tuple(sorted(findings, key=lambda f: _SEVERITY_ORDER[f.severity]))
