#!/usr/bin/env python3
"""Evaluation gate for Third-Party Risk Due-Diligence Agent (third-party-risk-ddq).

Two named layers via ``--mode`` (the scaffold is ``agent_eval_kit.eval_main``):

* **smoke** (default) - the offline pre-merge check CI runs on every change: it drives the REAL
  assessment pipeline (extraction, scoring, gap analysis, R8 routing) against a golden vendor set
  with SDK-free local adapters and scores five metrics against the dataset's OWN expected outcomes
  (an independent oracle), never against the pipeline's own verdict. * **gate** - the promotion
  verdict from the shared model-quality-gate authority (requires the ``gcp`` profile), via
  ``agent_eval_kit.PromotionGateClient``.

Every metric is proven able to go red in ``tests/unit/test_eval_metrics_go_red.py`` and
``tests/unit/test_not_falsely_green.py``, in both cases against the functions THIS module ships:
a metric that cannot go red is not a metric, and a red proof aimed at a local re-implementation
of the metric is not a proof about the gate.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from agent_eval_kit import EvalMetricResult, EvalReport, PromotionGateClient, eval_main
from pii_kit import pack_leak

from tprm_ddq.config import Settings, build_container
from tprm_ddq.domain.assessment_service import AssessmentService
from tprm_ddq.domain.evidence_ledger import EvidenceLedger
from tprm_ddq.domain.kernel import Severity
from tprm_ddq.domain.models import TriageInput
from tprm_ddq.domain.pii import PII_PATTERNS
from tprm_ddq.domain.tprm_models import (
    CanonicalControl,
    DataClassification,
    DocumentRef,
    Substitutability,
    VendorProfile,
)
from tprm_ddq.domain.triage_service import TriageService

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = _REPO_ROOT / "eval" / "datasets" / "golden_vendors.jsonl"
_AS_OF = date(2026, 1, 1)
_ACTOR = "eval-bot@bank.example"
_TENANT = "eval-tenant"

THRESHOLDS: dict[str, float] = {
    "scoring_accuracy": 0.80,
    "extraction_fidelity": 0.90,
    "gap_recall": 0.80,
    "review_safety": 1.0,
    "pii_safety": 0.99,
}
#: The registered model-quality-gate metric bundle for this vertical (model-quality-gate owns the
#: metrics + thresholds).
_BUNDLE = "third-party-risk-ddq"


def _load(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    if not cases:
        raise SystemExit(f"{path}: golden dataset is empty")
    return cases


def _mean(scores: list[float]) -> float:
    return round(sum(scores) / len(scores), 4) if scores else 0.0


def _profile(case: dict[str, Any]) -> VendorProfile:
    return VendorProfile(
        name=case["vendor"],
        service_criticality=Severity(case["criticality"]),
        data_classification=DataClassification(case["data_classification"]),
        jurisdiction=case["jurisdiction"],
        substitutability=Substitutability(case["substitutability"]),
    )


def _documents(case: dict[str, Any]) -> tuple[DocumentRef, ...]:
    content = "\n".join(case["documents"])
    return (DocumentRef(doc_id=f"evidence-{case['id']}", content=content, mime_type="text/plain"),)


def scoring_score(case: dict[str, Any]) -> float:
    """1.0 iff the engine's residual band equals the dataset's hand-derived expected band."""
    container = build_container(Settings(profile="local", audit_path=":memory:", tenant=_TENANT))
    assessment = _assess(container, case)
    return 1.0 if assessment.residual_band.value == case["expected_residual"] else 0.0


def extraction_score(case: dict[str, Any]) -> float:
    """Recall of the expected canonical controls from the documents (independent labels)."""
    expected = {CanonicalControl(c) for c in case["expected_controls"]}
    if not expected:
        return 1.0
    container = build_container(Settings(profile="local", audit_path=":memory:"))
    items: list[Any] = []
    for document in _documents(case):
        items.extend(container.extraction.extract(document).controls)
    present = EvidenceLedger(items=tuple(items)).controls_present()
    return round(len(expected & present) / len(expected), 4)


def gap_score(case: dict[str, Any]) -> float:
    """Recall of the expected gap controls in the engine's gap output (independent labels)."""
    expected = {CanonicalControl(c) for c in case["expected_gap_controls"]}
    if not expected:
        return 1.0
    container = build_container(Settings(profile="local", audit_path=":memory:", tenant=_TENANT))
    assessment = _assess(container, case)
    found = {gap.control for gap in assessment.gaps}
    return round(len(expected & found) / len(expected), 4)


def audit_texts(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Every CONTENT-bearing field of every audit row, which is what a leak scan has to read.

    Nothing here reads an audit row at all if the metric builds its own strings from the
    dataset (``redact(f"{p} on file", PII_PATTERNS)``) and then scanned those, which is a
    tautology: it scored the redactor against itself over text the service never produced, so it
    was green no matter what the service wrote. It has to read what was actually persisted, and
    that means the citations too: they travel inside the record and carry raw source text in
    ``snippet`` (``case.text[:80]``, an extracted document line) and in ``source_id`` (a locator
    built from the case subject, or ``<doc_id>:<lineno>``).

    ``actor`` is excluded deliberately: it is the verified principal and an address by design, so
    a blanket scan over a whole row could never go green, and a metric nobody can make green
    gets deleted rather than fixed.
    """
    texts: list[str] = []
    for row in rows:
        texts.append(str(row.get("redacted_summary", "")))
        texts.append(json.dumps(row.get("citations", []), sort_keys=True))
    return texts


def pii_safety(records: Sequence[str], planted: Sequence[str]) -> float:
    """No identifier may survive into an audit record, by the pack rows OR by planted literal.

    Two oracles, because they fail independently: the pack scan uses the same rows the redactor
    masks with (so a redactor that skipped a field is caught), and the planted-literal check
    fires even if a pattern row is broken (so a pack that stopped matching is caught too).
    """
    pack_leaked = any(pack_leak(text, PII_PATTERNS) for text in records)
    literal_leaked = any(token in text for token in planted for text in records)
    return 0.0 if (pack_leaked or literal_leaked) else 1.0


def planted_case(case: dict[str, Any]) -> TriageInput | None:
    """The dataset row as an input to the OTHER audit writer, or ``None`` if nothing is planted.

    ``TriageService`` is a shipped surface (the API route, the CLI and the agent tool all call
    it) and it is the second thing in this repository that writes an ``AuditEvent``, so the leak
    scan has to cover it. It is also the writer whose citations demonstrably carry raw client
    text offline: the locator is ``case:<subject>`` and the snippet is ``case.text[:80]``, where
    the assessment writer's offline citations are fixed FICTIONAL strings from the local research
    and compliance adapters. Feeding it the evidence line that CARRIES the planted identifier is
    the point: the metric has to be able to see a leak in the field the old one never read.
    """
    token = str(case.get("planted") or "")
    if not token:
        return None
    line = next((doc for doc in case["documents"] if token in doc), token)
    return TriageInput(subject=str(case["vendor"]), text=str(line))


def _assess(container: Any, case: dict[str, Any]) -> Any:
    service = AssessmentService(
        extraction=container.extraction,
        research=container.research,
        contract_terms=container.contract_terms,
        compliance=container.compliance,
        generation=container.generation,
        register_store=container.register_store,
        audit=container.audit,
        review_router=container.review_router,
    )
    return service.assess(
        _profile(case), _documents(case), actor=_ACTOR, tenant=_TENANT, as_of=_AS_OF
    )


def run_smoke(dataset: Path) -> EvalReport:
    cases = _load(dataset)

    scoring = [scoring_score(case) for case in cases]
    extraction = [extraction_score(case) for case in cases]
    gaps = [gap_score(case) for case in cases]

    # review_safety: every assessment must route to human-review-console and flag human review; zero
    # auto-accept.
    container = build_container(Settings(profile="local", audit_path=":memory:", tenant=_TENANT))
    service = AssessmentService(
        extraction=container.extraction,
        research=container.research,
        contract_terms=container.contract_terms,
        compliance=container.compliance,
        generation=container.generation,
        register_store=container.register_store,
        audit=container.audit,
        review_router=container.review_router,
    )
    reviewed = 0
    for case in cases:
        assessment = service.assess(
            _profile(case), _documents(case), actor=_ACTOR, tenant=_TENANT, as_of=_AS_OF
        )
        if assessment.requires_human_review:
            reviewed += 1
    routed = len(container.review_router.outbox.pending())
    review_safety = 1.0 if reviewed == len(cases) == routed else 0.0

    # pii_safety: no planted identifier may survive into any audit record the REAL services
    # wrote. The assessment loop above already wrote to `container.audit`; drive the other audit
    # writer into the SAME sink so the scan covers both, then read the sink back. `audit_texts`
    # decides WHICH fields count as the record's content, and see its docstring for why building
    # a string here and scanning that instead was a tautology.
    triage = TriageService(container.audit, tracer=container.tracer)
    for case in cases:
        planted_input = planted_case(case)
        if planted_input is not None:
            triage.triage(planted_input, actor=_ACTOR)
    records = audit_texts(container.audit.log.read_all())
    planted = [str(case["planted"]) for case in cases if case.get("planted")]

    results = (
        EvalMetricResult.scored("scoring_accuracy", _mean(scoring), THRESHOLDS["scoring_accuracy"]),
        EvalMetricResult.scored(
            "extraction_fidelity", _mean(extraction), THRESHOLDS["extraction_fidelity"]
        ),
        EvalMetricResult.scored("gap_recall", _mean(gaps), THRESHOLDS["gap_recall"]),
        EvalMetricResult.scored("review_safety", review_safety, THRESHOLDS["review_safety"]),
        EvalMetricResult.scored(
            "pii_safety", pii_safety(records, planted), THRESHOLDS["pii_safety"]
        ),
    )
    return EvalReport(dataset=str(dataset), results=results, n_examples=len(cases))


def run_gate(dataset: Path) -> tuple[EvalReport, bool]:
    settings = Settings.load()
    if settings.profile != "gcp":
        raise SystemExit(
            "--mode gate is the promotion authority and requires "
            f"TPRM_DDQ_PROFILE=gcp (got {settings.profile!r}); "
            "run --mode smoke for the offline pre-merge check."
        )
    client = PromotionGateClient(
        os.environ.get("TPRM_DDQ_QUALITY_URL", "http://localhost:8084"),
        bundle=_BUNDLE,
        model="gemini-3.5-flash",
    )
    return client.evaluate(str(dataset)), client.gate(str(dataset))


# Re-exported so the go-red test drives the exact functions the gate scores with.
__all__ = [
    "audit_texts",
    "extraction_score",
    "gap_score",
    "pii_safety",
    "planted_case",
    "run_smoke",
    "scoring_score",
]


if __name__ == "__main__":
    raise SystemExit(
        eval_main(
            smoke=run_smoke,
            gate=run_gate,
            default_dataset=DEFAULT_DATASET,
            description="Offline / model-quality-gate for third-party-risk-ddq.",
        )
    )
