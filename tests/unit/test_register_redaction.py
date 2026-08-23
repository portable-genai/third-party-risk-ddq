"""Nothing redaction removed survives into the vendor register either (check C3, second sink).

The WORM audit record was closed by construction in :class:`AuditEvent`, and the register was
left open: ``AssessmentService.assess`` hands the SAME citation tuple to ``_record``, which masks
it, and to ``RegisterEntry``, which did not. The register is not a lesser sink. It is
tenant-scoped, long-lived, read by Rgc9 over A2A as data, and an extraction citation carries
``snippet=line[:80]`` cut straight out of an uploaded document, so raw client text reached it
under a structural-looking name. That is the same class as the audit finding through a different
sink, which is why it is fixed the same way: at construction, not at the call site.

Scored the way the audit suite is: the shared pack's own rows, plus planted literals that still
fire if a pattern row is broken.

Not masked, deliberately: ``vendor`` and ``tenant``. They are the identity of the row, the pair
the store authorises on, and masking either would either erase the register's subject or break
tenant isolation. That mirrors ``AuditEvent.actor``, and it is why the scan below runs over the
content fields rather than over a whole row.
"""

from __future__ import annotations

from datetime import date

from pii_kit import pack_leak

from tprm_ddq.config import Settings, build_container
from tprm_ddq.domain.assessment_service import AssessmentService
from tprm_ddq.domain.kernel import Citation, Severity
from tprm_ddq.domain.pii import PII_PATTERNS
from tprm_ddq.domain.tprm_models import (
    DataClassification,
    DocumentRef,
    RegisterEntry,
    Substitutability,
    VendorProfile,
)

from tests.fixtures import sample_cases

_PLANTED = (sample_cases.PLANTED_NRIC, sample_cases.PLANTED_EMAIL)
_AS_OF = date(2026, 1, 1)
_TENANT = "demo-bank"
_ACTOR = "analyst@bank.example"
_VENDOR = "Cornerstone Payments Inc (FICTIONAL)"


def _service(container: object) -> AssessmentService:
    c = container
    return AssessmentService(
        extraction=c.extraction,  # type: ignore[attr-defined]
        research=c.research,  # type: ignore[attr-defined]
        contract_terms=c.contract_terms,  # type: ignore[attr-defined]
        compliance=c.compliance,  # type: ignore[attr-defined]
        generation=c.generation,  # type: ignore[attr-defined]
        register_store=c.register_store,  # type: ignore[attr-defined]
        audit=c.audit,  # type: ignore[attr-defined]
        review_router=c.review_router,  # type: ignore[attr-defined]
    )


def _profile() -> VendorProfile:
    return VendorProfile(
        name=_VENDOR,
        service_criticality=Severity.HIGH,
        data_classification=DataClassification.CONFIDENTIAL,
        jurisdiction="XX",
        substitutability=Substitutability.MODERATE,
    )


def _planted_documents() -> tuple[DocumentRef, ...]:
    """An evidence file whose control line carries an identifier, as a real upload would.

    The weak-control gap cites ``items[0].citation``, the extraction citation, whose snippet is
    the first 80 characters of this line. Both planted literals sit inside that window on
    purpose: a truncated snippet would make the test pass for the wrong reason.
    """
    content = "\n".join(
        [
            (
                "CONTROL soc2 CC6.6 ineffective 2025-06-01 "
                f"NRIC {sample_cases.PLANTED_NRIC} {sample_cases.PLANTED_EMAIL}"
            ),
            "CONTROL soc2 C1.1 ineffective 2025-06-01",
            "CONTROL iso27001 A.5.29 untested 2022-01-01 expired",
        ]
    )
    return (DocumentRef(doc_id="ev", content=content, mime_type="text/plain"),)


def _citation_content(entry: RegisterEntry) -> str:
    """Every content-bearing field of the row's citations, as one scannable blob."""
    return " ".join(f"{c.source_id} {c.title} {c.snippet}" for c in entry.citations)


def test_the_planted_identifier_is_inside_the_snippet_window() -> None:
    """Guards the fixture itself: an 80-character cut that dropped the literal proves nothing."""
    line = _planted_documents()[0].content.splitlines()[0]
    snippet = line[:80]
    for token in _PLANTED:
        assert token in snippet, f"fixture is wrong: {token!r} falls outside the snippet window"


def test_no_identifier_reaches_the_vendor_register() -> None:
    """The end-to-end leak path: an uploaded document line, through a gap, into the register."""
    container = build_container(Settings(profile="local", audit_path=":memory:", tenant=_TENANT))
    service = _service(container)
    service.assess(_profile(), _planted_documents(), actor=_ACTOR, tenant=_TENANT, as_of=_AS_OF)

    entry = container.register_store.get(_VENDOR, tenant=_TENANT)
    assert entry is not None, "the assessment must write a register row"
    assert entry.citations, "the row must carry its citations; an empty tuple would pass vacuously"

    blob = _citation_content(entry)
    assert not pack_leak(blob, PII_PATTERNS), f"pack row matched in the register: {blob}"
    for token in _PLANTED:
        assert token not in blob, f"planted {token!r} survived into the register: {blob}"


def test_the_register_row_masks_its_citations_at_construction() -> None:
    """A surface added later cannot leak by forgetting, which is the point of the fix.

    The end-to-end test above proves today's writer is clean. This one proves the NEXT writer is
    too, without it having to remember: the masking is a property of the row, not of the caller.
    """
    entry = RegisterEntry(
        vendor=_VENDOR,
        tenant=_TENANT,
        residual_band=Severity.HIGH,
        material=True,
        as_of=_AS_OF,
        citations=(
            Citation(
                source_id=f"case:{sample_cases.PLANTED_NRIC}",
                title=f"file from {sample_cases.PLANTED_EMAIL}",
                snippet=f"breach, NRIC {sample_cases.PLANTED_NRIC}",
            ),
        ),
    )
    blob = _citation_content(entry)
    assert not pack_leak(blob, PII_PATTERNS), f"pack row matched at construction: {blob}"
    for token in _PLANTED:
        assert token not in blob, f"planted {token!r} survived construction: {blob}"


def test_the_row_identity_is_not_masked() -> None:
    """Redaction must not eat the columns the store authorises on.

    A blanket mask over the whole row would break tenant isolation and erase the register's
    subject, so the boundary is content-only. Pinned here so a later "mask everything" change
    fails loudly rather than silently making every row unfindable.
    """
    entry = RegisterEntry(
        vendor=_VENDOR,
        tenant=_TENANT,
        residual_band=Severity.HIGH,
        material=True,
        as_of=_AS_OF,
    )
    assert entry.vendor == _VENDOR
    assert entry.tenant == _TENANT
