"""Local DocumentExtractionPort: a deterministic parser over a fictional fixture format.

Real, replayable extraction (not a stub): it parses a small line-based evidence format that the
fixture corpus and the demo use, mapping each framework identifier to a canonical control through
``control_taxonomy``. That makes extraction fidelity measurable against golden labels while
keeping the offline profile SDK-free. Lines:

    CONTROL <framework> <identifier> <effectiveness> <iso-date> [adverse|expired]
    DDQ <framework> <identifier> <free text answer...>
    FIN current_assets=.. current_liabilities=.. total_debt=.. total_equity=.. going_concern=..

Anything else is kept only in ``full_text``. An identifier the taxonomy pack does not know is
dropped from the structured output (the caller surfaces it as an unmapped-evidence gap), never
guessed into a nearby control.
"""

from __future__ import annotations

from datetime import date

from ...config import Settings
from ...domain.control_taxonomy import map_control
from ...domain.kernel import Citation
from ...domain.tprm_models import (
    ControlEffectiveness,
    DocumentRef,
    EvidenceItem,
    EvidenceKind,
    ExtractedDocument,
    FinancialFigures,
    RawDDQAnswer,
)

_KIND_BY_FRAMEWORK: dict[str, EvidenceKind] = {
    "soc2": EvidenceKind.SOC2,
    "iso27001": EvidenceKind.ISO_CERT,
    "sig_caiq": EvidenceKind.DDQ_ANSWER,
}


class LocalExtractionAdapter:
    """Parse the fixture evidence format deterministically. Same document, same extract."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def extract(self, document: DocumentRef) -> ExtractedDocument:
        controls: list[EvidenceItem] = []
        answers: list[RawDDQAnswer] = []
        figures: FinancialFigures | None = None
        for lineno, raw in enumerate(document.content.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            tag, _, rest = line.partition(" ")
            citation = Citation(
                source_id=f"{document.doc_id}:{lineno}",
                title=document.doc_id,
                snippet=line[:80],
            )
            if tag == "CONTROL":
                item = self._parse_control(rest, citation)
                if item is not None:
                    controls.append(item)
            elif tag == "DDQ":
                answers.append(self._parse_ddq(rest, citation))
            elif tag == "FIN":
                figures = self._parse_fin(rest, citation)
        return ExtractedDocument(
            doc_id=document.doc_id,
            mime_type=document.mime_type,
            full_text=document.content,
            controls=tuple(controls),
            ddq_answers=tuple(answers),
            figures=figures,
        )

    @staticmethod
    def _parse_control(rest: str, citation: Citation) -> EvidenceItem | None:
        parts = rest.split()
        if len(parts) < 4:
            return None
        framework, identifier, eff, iso = parts[0], parts[1], parts[2], parts[3]
        control = map_control(framework, identifier)
        if control is None:
            return None
        flags = parts[4:]
        return EvidenceItem(
            control=control,
            kind=_KIND_BY_FRAMEWORK.get(framework, EvidenceKind.DDQ_ANSWER),
            effectiveness=ControlEffectiveness(eff),
            as_of=date.fromisoformat(iso),
            citation=citation,
            adverse_opinion="adverse" in flags,
            expired="expired" in flags,
        )

    @staticmethod
    def _parse_ddq(rest: str, citation: Citation) -> RawDDQAnswer:
        framework, _, tail = rest.partition(" ")
        identifier, _, text = tail.partition(" ")
        control = map_control(framework, identifier)
        return RawDDQAnswer(control=control, answer_text=text.strip(), citation=citation)

    @staticmethod
    def _parse_fin(rest: str, citation: Citation) -> FinancialFigures:
        fields: dict[str, str] = {}
        for token in rest.split():
            key, _, value = token.partition("=")
            fields[key] = value
        return FinancialFigures(
            current_assets=float(fields.get("current_assets", "0") or "0"),
            current_liabilities=float(fields.get("current_liabilities", "0") or "0"),
            total_debt=float(fields.get("total_debt", "0") or "0"),
            total_equity=float(fields.get("total_equity", "0") or "0"),
            going_concern_flag=fields.get("going_concern", "false").lower() == "true",
            citation=citation,
        )
