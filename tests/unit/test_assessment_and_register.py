"""The assessment orchestrator routes R8, writes the register, and refuses cross-tenant reads.

These prove the consequential end-to-end behaviour the plan requires: a memo is always routed to
Hrz7 (never merely flagged), the register row is materiality-flagged by policy, and a read for a
tenant other than the verified principal's is a denial, not a miss.
"""

from __future__ import annotations

from datetime import date

import pytest

from tprm_ddq.config import Settings, build_container
from tprm_ddq.domain.assessment_service import AssessmentService
from tprm_ddq.domain.errors import CrossTenantError
from tprm_ddq.domain.kernel import Severity
from tprm_ddq.domain.register_service import RegisterService
from tprm_ddq.domain.tprm_models import (
    DataClassification,
    DocumentRef,
    RegisterEntry,
    Substitutability,
    VendorProfile,
)

_AS_OF = date(2026, 1, 1)
_TENANT = "demo-bank"
_OTHER = "rival-bank"
_ACTOR = "analyst@bank.example"


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
        name="Cornerstone Payments Inc (FICTIONAL)",
        service_criticality=Severity.HIGH,
        data_classification=DataClassification.CONFIDENTIAL,
        jurisdiction="XX",
        substitutability=Substitutability.MODERATE,
    )


def _documents() -> tuple[DocumentRef, ...]:
    content = "\n".join(
        [
            "CONTROL soc2 CC6.6 ineffective 2025-06-01",
            "CONTROL soc2 C1.1 ineffective 2025-06-01",
            "CONTROL iso27001 A.5.29 untested 2022-01-01 expired",
        ]
    )
    return (DocumentRef(doc_id="ev", content=content, mime_type="text/plain"),)


def test_assessment_routes_the_memo_and_flags_review() -> None:
    container = build_container(Settings(profile="local", audit_path=":memory:", tenant=_TENANT))
    service = _service(container)
    assessment = service.assess(
        _profile(), _documents(), actor=_ACTOR, tenant=_TENANT, as_of=_AS_OF
    )
    assert assessment.requires_human_review is True
    assert assessment.residual_band == Severity.HIGH
    # R8: the memo reached the review outbox, it was not merely flagged.
    assert len(container.review_router.outbox.pending()) == 1
    # The consequential summary is audited (already redacted).
    assert container.audit.log.read_all(), "the assessment must be audited"


def test_register_entry_is_material_flagged_by_policy() -> None:
    container = build_container(Settings(profile="local", audit_path=":memory:", tenant=_TENANT))
    service = _service(container)
    service.assess(_profile(), _documents(), actor=_ACTOR, tenant=_TENANT, as_of=_AS_OF)
    entry = container.register_store.get(_profile().name, tenant=_TENANT)
    assert entry is not None
    assert entry.material is True, "a high-residual arrangement is material by policy"


def test_register_read_denies_cross_tenant_with_403_not_404() -> None:
    container = build_container(Settings(profile="local", audit_path=":memory:", tenant=_TENANT))
    reg = RegisterService(container.register_store)
    reg.upsert(
        RegisterEntry(
            vendor="Cornerstone Payments Inc (FICTIONAL)",
            tenant=_TENANT,
            residual_band=Severity.HIGH,
            material=True,
            as_of=_AS_OF,
        ),
        principal_tenant=_TENANT,
    )
    with pytest.raises(CrossTenantError) as caught:
        reg.get(
            "Cornerstone Payments Inc (FICTIONAL)",
            requested_tenant=_OTHER,
            principal_tenant=_TENANT,
        )
    assert caught.value.status_code == 403


def test_generation_stub_does_not_move_the_number() -> None:
    """The determinism invariant: with generation stubbed, the residual band is unchanged."""
    container = build_container(Settings(profile="local", audit_path=":memory:", tenant=_TENANT))
    first = _service(container).assess(
        _profile(), _documents(), actor=_ACTOR, tenant=_TENANT, as_of=_AS_OF
    )
    container2 = build_container(Settings(profile="local", audit_path=":memory:", tenant=_TENANT))
    second = _service(container2).assess(
        _profile(), _documents(), actor=_ACTOR, tenant=_TENANT, as_of=_AS_OF
    )
    assert first.residual_band == second.residual_band
    assert first.inherent_band == second.inherent_band
    assert first.residual_points == second.residual_points
