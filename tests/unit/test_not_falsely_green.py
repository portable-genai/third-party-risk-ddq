"""The pii_safety metric the GATE SHIPS is proved able to go red (check E2).

The previous version of this file scored a local one-line helper defined three lines above the
assertion. It passed, and it proved nothing about the gate, because the shipped metric never
touched the service at all. It built its own strings out of the dataset and scanned those::

    planted  = [str(case["planted"]) for case in cases if case.get("planted")]
    redacted = [redact(f"{p} on file", PII_PATTERNS) for p in planted]

which is a tautology: it scored the redactor against itself over a string the service never
produced, so it reported ``pii_safety 1.000 PASS`` whatever the audit records held.

So the falsification runs against ``eval.run_eval`` itself, imported as the gate imports it, and
the mutant is the leak the metric exists to catch: the SAME row, summary clean either way,
differing only in the citation. A metric that reads the wrong field, or that reads no field at
all, cannot tell the two apart and stays green on the red input, which is exactly the failure
``assert_can_go_red`` refuses.
"""

from __future__ import annotations

from typing import Any

from agent_eval_kit import assert_can_go_red
from eval.run_eval import THRESHOLDS, audit_texts, pii_safety, planted_case

from tprm_ddq.adapters.local.audit import LocalAuditAdapter
from tprm_ddq.adapters.local.tracer import LocalNoopTracerAdapter
from tprm_ddq.config import Settings
from tprm_ddq.domain.triage_service import TriageService

from tests.fixtures import sample_cases

_PLANTED = (sample_cases.PLANTED_NRIC,)

#: The summary is CLEAN in both rows. That is the whole point: the summary was never the field
#: that leaked, so a metric that only reads it scores these two identically, and the metric that
#: read nothing at all scored them identically too.
_CLEAN_ROW: dict[str, Any] = {
    "action": "triage",
    "actor": sample_cases.ACTOR,
    "redacted_summary": "Gamma LLP (FICTIONAL): triaged high :: NRIC [REDACTED:SG_NRIC_FIN]",
    "citations": [
        {
            "source_id": "case:Gamma LLP (FICTIONAL)",
            "title": "Case description",
            "snippet": "urgent breach, NRIC [REDACTED:SG_NRIC_FIN] on file",
        }
    ],
}

#: Redaction off, in the citation only (the mutant the shipped metric could not have seen).
_LEAKY_ROW: dict[str, Any] = {
    **_CLEAN_ROW,
    "citations": [
        {
            "source_id": f"case:Gamma LLP (FICTIONAL) {sample_cases.PLANTED_NRIC}",
            "title": "Case description",
            "snippet": f"urgent breach, NRIC {sample_cases.PLANTED_NRIC} on file",
        }
    ],
}


def _score(rows: list[dict[str, Any]]) -> float:
    """The gate's own scorer over the gate's own field selection. No re-implementation here."""
    return pii_safety(audit_texts(rows), _PLANTED)


def test_pii_safety_can_go_red() -> None:
    assert_can_go_red(
        _score,
        green=[_CLEAN_ROW],
        red=[_LEAKY_ROW],
        threshold=THRESHOLDS["pii_safety"],
        metric="pii_safety",
    )


def test_pii_safety_is_green_on_the_record_the_real_service_writes() -> None:
    """Green, and green over a real run rather than over a string the metric wrote itself."""
    settings = Settings(profile="local", audit_path=":memory:")
    audit = LocalAuditAdapter(settings)
    TriageService(audit, tracer=LocalNoopTracerAdapter(settings)).triage(
        sample_cases.PII_SUBJECT_CASE, actor=sample_cases.ACTOR
    )

    texts = audit_texts(audit.log.read_all())
    assert any("[REDACTED:" in text for text in texts), (
        "the scan found no redaction marker, so it is reading fields that carry no content "
        "and its green means nothing"
    )
    assert pii_safety(texts, (*_PLANTED, sample_cases.PLANTED_EMAIL)) == 1.0


def test_the_scan_excludes_the_actor_so_it_can_ever_be_green() -> None:
    """The caveat, pinned: widening this to whole rows makes the metric permanently red.

    ``actor`` is the verified principal and is an address by design. A well-meaning "scan the
    whole record" change would make every run fail on the attribution column, and the next
    person would relax the threshold rather than narrow the scan.
    """
    row: dict[str, Any] = {**_CLEAN_ROW, "actor": "analyst@bank.example"}
    assert pii_safety(audit_texts([row]), _PLANTED) == 1.0


def test_the_metric_drives_a_writer_whose_citations_carry_the_planted_identifier() -> None:
    """The scan must have something to find, or its green is an accident of empty inputs.

    ``planted_case`` picks the evidence LINE that carries the identifier, so the audit row the
    scan reads genuinely contains it pre-redaction. Without this, a dataset whose planted token
    never reaches a record would keep the metric green for the wrong reason.
    """
    case: dict[str, Any] = {
        "vendor": "Cornerstone Payments Inc (FICTIONAL)",
        "planted": sample_cases.PLANTED_NRIC,
        "documents": [
            "CONTROL soc2 CC6.1 partial 2025-06-01",
            f"DDQ sig_caiq DSP data residency planned NRIC {sample_cases.PLANTED_NRIC}",
        ],
    }
    triage_input = planted_case(case)
    assert triage_input is not None
    assert sample_cases.PLANTED_NRIC in triage_input.text
    assert planted_case({"vendor": "X", "planted": None, "documents": []}) is None
