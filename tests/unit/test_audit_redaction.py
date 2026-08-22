"""Nothing redaction removed survives anywhere else in the WORM record (check C3).

Both audit writers (``TriageService._triage`` and ``AssessmentService._record``) masked
``redacted_summary`` and then handed the SAME event their citations untouched, so the identifier
the summary no longer carried was persisted verbatim one field away, in a record that is by
design immutable and long-retained. The summary is not the record.

Two rules this suite holds, and they pull in opposite directions, which is why both are written
down:

* every CONTENT field is scanned: the summary, and each citation's locator, title and snippet.
  The triage locator is built from the case subject and the snippet is cut from the case text,
  and an extraction locator is ``<doc_id>:<lineno>`` over an uploaded document, so all of them
  are raw client text with a structural-looking name.
* the ATTRIBUTION field is not. ``actor`` is the verified principal and is an address by design,
  so a blanket scan over a whole audit row could never go green, and a scan that "fixed" that by
  masking the actor would erase the only column that says who acted.

Scored two ways, as the eval metric is: the shared pack's own rows, plus the planted literals,
which still fire if a pattern row is broken.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from typing import Any

import pytest
from pii_kit import pack_leak

from tprm_ddq.adapters._review_payload import result_to_review
from tprm_ddq.adapters.local.audit import LocalAuditAdapter
from tprm_ddq.domain.assessment_service import AssessmentService
from tprm_ddq.domain.kernel import AuditEvent, Citation, Decision, Severity
from tprm_ddq.domain.models import TriageInput
from tprm_ddq.domain.pii import PII_PATTERNS
from tprm_ddq.domain.tprm_models import (
    DataClassification,
    DocumentRef,
    Substitutability,
    VendorProfile,
)
from tprm_ddq.domain.triage_service import TriageService

from tests.fixtures import sample_cases

_PLANTED = (sample_cases.PLANTED_NRIC, sample_cases.PLANTED_EMAIL)
_AS_OF = date(2026, 1, 1)


def _content(row: Mapping[str, Any]) -> str:
    """Every content-bearing field of one audit row, as one scannable blob.

    ``actor`` and the structural columns are excluded deliberately: see the module docstring.
    """
    return " ".join(
        (
            str(row.get("redacted_summary", "")),
            json.dumps(row.get("citations", []), sort_keys=True),
        )
    )


def _assert_clean(audit: object) -> None:
    assert isinstance(audit, LocalAuditAdapter)
    rows = list(audit.log.read_all())
    assert rows, "the real path wrote no audit record, so this proves nothing"
    for row in rows:
        blob = _content(row)
        assert not pack_leak(blob, PII_PATTERNS), f"pack row matched in the WORM record: {blob}"
        for token in _PLANTED:
            assert token not in blob, f"planted {token!r} survived into the WORM record: {blob}"


@pytest.mark.parametrize(
    "case",
    [sample_cases.PII_CASE, sample_cases.PII_SUBJECT_CASE],
    ids=["identifier-in-text", "identifier-in-subject-and-text"],
)
def test_no_identifier_reaches_the_triage_audit_record(
    triage_service: TriageService, container: Any, case: TriageInput
) -> None:
    triage_service.triage(case, actor=sample_cases.ACTOR)
    _assert_clean(container.audit)


def test_any_audit_event_is_masked_at_construction_whatever_the_caller_passed() -> None:
    """The invariant itself: the TYPE holds the boundary, so no surface can leak by forgetting.

    This is what ``AssessmentService._record`` and any surface added later actually do, spelled
    out: hand ``AuditEvent`` a summary and citations straight off the engine. Before the fix a
    caller that forgot ``redact`` wrote the identifier into the WORM record in whichever field it
    forgot; now every content field comes back masked and only ``actor`` survives verbatim.
    """
    event = AuditEvent(
        action="assess",
        actor=sample_cases.ACTOR,
        decision=Decision.ESCALATED,
        severity=Severity.HIGH,
        redacted_summary=f"Delta Vendor: NRIC {sample_cases.PLANTED_NRIC} on file",
        citations=(
            Citation(
                source_id=f"media:delta:{sample_cases.PLANTED_NRIC}",
                title=f"Adverse media on NRIC {sample_cases.PLANTED_NRIC}",
                snippet=f"reported contact {sample_cases.PLANTED_EMAIL}",
            ),
        ),
    )

    blob = " ".join(
        (
            event.redacted_summary,
            *(f"{c.source_id} {c.title} {c.snippet}" for c in event.citations),
        )
    )
    assert not pack_leak(blob, PII_PATTERNS), f"pack row matched at construction: {blob}"
    for token in _PLANTED:
        assert token not in blob, f"planted {token!r} survived construction: {blob}"
    assert event.actor == sample_cases.ACTOR


def test_no_identifier_reaches_the_assessment_audit_record(container: Any) -> None:
    """The other audit writer, driven end to end, with the identifier in the vendor and the docs.

    This one is GREEN even without the fix, and that is worth writing down rather than hiding:
    offline, every citation this record carries comes from the local research and compliance
    adapters as fixed FICTIONAL strings, so the pre-fix leak channel is empty here. Under the
    managed profile the adverse-media citations are external prose, which is exactly the shape
    the triage test above catches, so this is the standing gate that keeps the second writer
    honest when those adapters stop being fixtures.
    """
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
    profile = VendorProfile(
        name=f"Delta Vendor Pte Ltd (FICTIONAL) NRIC {sample_cases.PLANTED_NRIC}",
        service_criticality=Severity.HIGH,
        data_classification=DataClassification.CONFIDENTIAL,
        jurisdiction="SG",
        substitutability=Substitutability.MODERATE,
    )
    documents = (
        DocumentRef(
            doc_id=f"evidence-{sample_cases.PLANTED_NRIC}",
            content=(
                "CONTROL soc2 CC6.1 partial 2025-06-01\n"
                f"DDQ sig_caiq SEF incident contact {sample_cases.PLANTED_EMAIL}\n"
            ),
            mime_type="text/plain",
        ),
    )
    service.assess(
        profile, documents, actor=sample_cases.ACTOR, tenant=sample_cases.TENANT, as_of=_AS_OF
    )
    _assert_clean(container.audit)


def test_the_actor_is_kept_verbatim_because_it_is_attribution(
    triage_service: TriageService, container: Any
) -> None:
    """The caveat, pinned: the principal is an address and must NOT be masked away."""
    triage_service.triage(sample_cases.PII_CASE, actor=sample_cases.ACTOR)

    audit = container.audit
    assert isinstance(audit, LocalAuditAdapter)
    actors = [str(row.get("actor", "")) for row in audit.log.read_all()]
    assert actors == [sample_cases.ACTOR]


def test_the_whole_review_payload_is_redacted_not_only_its_narrative_fields(
    triage_service: TriageService,
) -> None:
    """Every field that crosses to the console, including the ones with structural names.

    ``subject`` and ``summary`` were masked and ``case_ref`` and ``source_key`` were not, so the
    identifier the payload had just removed from two fields crossed the wire in the two beside
    them. A citation LOCATOR is the same trap one level down. The scan is over the SERIALISED
    payload rather than a chosen list of fields, so a field added later is covered by default.
    """
    result = triage_service.triage(sample_cases.PII_SUBJECT_CASE, actor=sample_cases.ACTOR)
    review = result_to_review(result, maker=sample_cases.ACTOR, tenant=sample_cases.TENANT)

    blob = json.dumps(
        {
            "subject": review.subject,
            "summary": review.summary,
            "case_ref": review.case_ref,
            "source_key": review.source_key,
            "sod_group": review.sod_group,
            "citations": [
                {"source_id": c.source_id, "title": c.title, "snippet": c.snippet}
                for c in review.citations
            ],
        },
        sort_keys=True,
    )
    assert not pack_leak(blob, PII_PATTERNS), f"pack row matched in the review payload: {blob}"
    for token in _PLANTED:
        assert token not in blob, f"planted {token!r} crossed to the console: {blob}"


def test_the_review_source_key_is_stable_across_retries(
    triage_service: TriageService,
) -> None:
    """A redacted idempotency key is only a key if it is the SAME key on the retry.

    ``pii_kit.redact`` substitutes a fixed token per pattern rather than a per-call surrogate,
    so the masked subject is deterministic. Pinned here because the whole trade above depends on
    it: a key that varied per call would turn one retried delivery into many reviews.
    """
    result = triage_service.triage(sample_cases.PII_SUBJECT_CASE, actor=sample_cases.ACTOR)
    keys = {
        result_to_review(result, maker=sample_cases.ACTOR, tenant=sample_cases.TENANT).source_key
        for _ in range(50)
    }
    assert len(keys) == 1, f"the idempotency key is not stable across retries: {keys}"
    assert sample_cases.PLANTED_NRIC not in next(iter(keys))
