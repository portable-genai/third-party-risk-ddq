"""ONE canonical request per port, shared by the structural and behavioural contract suites.

Parity means the same request through every implementation, so the request needs a single home.
Retyping it per suite is how two "parity" tests end up asserting different things.

Each :class:`PortCase` answers three questions about one port:

* ``invoke``   : what a single canonical call to this port looks like;
* ``answered`` : what it means for the OFFLINE family to have actually answered (a port that
  returns ``None`` and records nothing has not answered, it has merely not raised);
* ``managed_refusal`` : what the MANAGED family must do when called with no cloud reachable.
  Never a silent success: either it refuses because it is unconfigured, or its lazy SDK import
  fails. Both are honest; returning as if the work happened is not.

Adding a port means adding a case here. ``test_port_parity.py`` fails the build if this table
and the port map ever disagree, so the touch list in ``CONTRIBUTING.md`` is enforced rather than
merely written down.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from agent_eval_kit import EvalReport
from hex_service_kit.identity import IdentityError, Principal, RequestContext
from hex_service_kit.observability import TokenUsage

from tprm_ddq.domain.kernel import (
    AuditEvent,
    Citation,
    Decision,
    Severity,
)
from tprm_ddq.domain.models import (
    TriageResult,
)
from tprm_ddq.domain.tprm_models import (
    CanonicalControl,
    DocumentRef,
    RegisterEntry,
)

from tests.fixtures import sample_cases

#: The audit record every audit-port implementation is handed. Already redacted, as the port
#: requires: a raw identifier must never reach a WORM record.
CANONICAL_EVENT = AuditEvent(
    action="triage",
    actor=sample_cases.ACTOR,
    decision=Decision.ESCALATED,
    severity=Severity.HIGH,
    redacted_summary="Acme Holdings (FICTIONAL): triaged high",
    citations=(Citation(source_id="case:acme", title="Case description", snippet="urgent"),),
)

#: The escalated result every review-router implementation is handed (rule R8's payload).
CANONICAL_RESULT = TriageResult(
    subject=sample_cases.ESCALATING_CASE.subject,
    severity=Severity.HIGH,
    decision=Decision.ESCALATED,
    summary=f"{sample_cases.ESCALATING_CASE.subject}: triaged high",
    requires_human_review=True,
    citations=(Citation(source_id="case:acme", title="Case description", snippet="urgent"),),
)

#: The inbound transport context every identity implementation is handed.
CANONICAL_CONTEXT = RequestContext(headers={"x-dev-persona": "auditor"})

#: One evidence document every extraction implementation is handed (the fixture line format).
CANONICAL_DOCUMENT = DocumentRef(
    doc_id="soc2-nimbus",
    content="CONTROL soc2 CC6.1 effective 2025-01-10\nDDQ sig_caiq IAM we enforce MFA everywhere",
    mime_type="text/plain",
)

#: The register entry every register-store implementation is handed.
CANONICAL_ENTRY = RegisterEntry(
    vendor="Nimbus Cloud Services (FICTIONAL)",
    tenant=sample_cases.TENANT,
    residual_band=Severity.HIGH,
    material=False,
    as_of=date(2026, 1, 1),
)

#: The controls every compliance implementation is asked about.
CANONICAL_CONTROLS = (CanonicalControl.ACCESS_CONTROL, CanonicalControl.ENCRYPTION)

#: The subject every adverse-media implementation is asked about (a corpus hit).
CANONICAL_MEDIA_SUBJECT = "Cornerstone Payments Inc (FICTIONAL)"

#: The vendor every contract-terms implementation is asked about (a fixture register hit).
CANONICAL_CONTRACT_VENDOR = "Nimbus Cloud Services (FICTIONAL)"


@dataclass(frozen=True, slots=True)
class PortCase:
    """One port's canonical call plus the two verdicts the parity suites need."""

    invoke: Callable[[Any], Any]
    answered: Callable[[Any, Any], bool]
    managed_refusal: tuple[type[BaseException], ...]
    detail: str


def _audit_invoke(adapter: Any) -> Any:
    return adapter.record(CANONICAL_EVENT)


def _audit_answered(adapter: Any, _result: Any) -> bool:
    stored = adapter.log.read_all()
    return bool(stored) and stored[-1]["actor"] == sample_cases.ACTOR and adapter.verify().ok


def _identity_invoke(adapter: Any) -> Any:
    return adapter.resolve(CANONICAL_CONTEXT)


def _identity_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, Principal) and bool(result.actor)


def _review_invoke(adapter: Any) -> Any:
    return adapter.route(CANONICAL_RESULT, maker=sample_cases.ACTOR, tenant=sample_cases.TENANT)


def _review_answered(adapter: Any, result: Any) -> bool:
    return bool(result) and len(adapter.outbox.pending()) == 1


def _extraction_invoke(adapter: Any) -> Any:
    return adapter.extract(CANONICAL_DOCUMENT)


def _extraction_answered(_adapter: Any, result: Any) -> bool:
    return bool(result.controls) and bool(result.full_text)


def _contract_invoke(adapter: Any) -> Any:
    return adapter.commitments(CANONICAL_CONTRACT_VENDOR, tenant=sample_cases.TENANT)


def _contract_answered(_adapter: Any, result: Any) -> bool:
    return len(result) > 0


def _research_invoke(adapter: Any) -> Any:
    return adapter.search(CANONICAL_MEDIA_SUBJECT)


def _research_answered(_adapter: Any, result: Any) -> bool:
    return len(result) > 0


def _compliance_invoke(adapter: Any) -> Any:
    return adapter.requirements(CANONICAL_CONTROLS, actor=sample_cases.ACTOR)


def _compliance_answered(_adapter: Any, result: Any) -> bool:
    return len(result) > 0


def _register_invoke(adapter: Any) -> Any:
    return adapter.upsert(CANONICAL_ENTRY)


def _register_answered(adapter: Any, result: Any) -> bool:
    stored = adapter.get(CANONICAL_ENTRY.vendor, tenant=CANONICAL_ENTRY.tenant)
    return bool(result) and stored is not None and stored.material is True


def _generation_invoke(adapter: Any) -> Any:
    return adapter.draft_memo("Nimbus Cloud Services (FICTIONAL)", "high", ("gap-1",))


def _generation_answered(_adapter: Any, result: Any) -> bool:
    return bool(result) and "Nimbus" in str(result)


def _tracer_invoke(adapter: Any) -> Any:
    with adapter.span("canonical.unit", action="canonical"):
        adapter.record_token_usage(TokenUsage(input_tokens=7, output_tokens=2), "canonical-model")
    return True


def _tracer_answered(adapter: Any, result: Any) -> bool:
    return bool(result)


def _evaluation_invoke(adapter: Any) -> Any:
    return adapter.evaluate("eval/datasets/canonical.jsonl")


def _evaluation_answered(adapter: Any, result: Any) -> bool:
    return isinstance(result, EvalReport) and result.dataset.endswith("canonical.jsonl")


CANONICAL_CALLS: dict[str, PortCase] = {
    "audit": PortCase(
        invoke=_audit_invoke,
        answered=_audit_answered,
        # The lazy `google.cloud` import is the first thing the managed sink does.
        managed_refusal=(ImportError,),
        detail="write one already-redacted WORM record",
    ),
    "identity": PortCase(
        invoke=_identity_invoke,
        answered=_identity_answered,
        # No IAP assertion header offline, so the managed adapter refuses before importing.
        managed_refusal=(IdentityError,),
        detail="resolve a verified principal from transport context",
    ),
    "review_router": PortCase(
        invoke=_review_invoke,
        answered=_review_answered,
        # Rule R8: with no console configured the managed router must refuse, not swallow.
        managed_refusal=(RuntimeError,),
        detail="route one escalated result to human review",
    ),
    "extraction": PortCase(
        invoke=_extraction_invoke,
        answered=_extraction_answered,
        # The lazy `google.cloud.documentai` import is the first thing the managed sink does.
        managed_refusal=(ImportError, RuntimeError),
        detail="extract structured fields plus full text from a document",
    ),
    "contract_terms": PortCase(
        invoke=_contract_invoke,
        answered=_contract_answered,
        # No contract-obligation-extraction endpoint configured, so the managed A2A client refuses.
        managed_refusal=(ImportError, RuntimeError),
        detail="return the vendor's contractual commitments",
    ),
    "research": PortCase(
        invoke=_research_invoke,
        answered=_research_answered,
        # The grounded sub-agent's SDK import is the first thing the managed adapter does.
        managed_refusal=(ImportError, RuntimeError),
        detail="return severity-ordered adverse-media findings",
    ),
    "compliance": PortCase(
        invoke=_compliance_invoke,
        answered=_compliance_answered,
        # No compliance-advisory endpoint configured, so the managed A2A client refuses.
        managed_refusal=(ImportError, RuntimeError),
        detail="fetch outsourcing-rule expectations for controls",
    ),
    "register_store": PortCase(
        invoke=_register_invoke,
        answered=_register_answered,
        # The lazy AlloyDB connector import is the first thing the managed store does.
        managed_refusal=(ImportError, RuntimeError),
        detail="persist and read back a tenant-scoped register entry",
    ),
    "generation": PortCase(
        invoke=_generation_invoke,
        answered=_generation_answered,
        # The lazy Gemini SDK import is the first thing the managed adapter does.
        managed_refusal=(ImportError, RuntimeError),
        detail="draft narration grounded in engine output",
    ),
    "tracer": PortCase(
        invoke=_tracer_invoke,
        answered=_tracer_answered,
        # NOTHING. Tracing is not essential to correctness, so the managed adapter must not refuse
        # offline either: with no SDK it degrades to a no-op and the traced body still runs. An
        # adapter that raised here would take a request down over a diagnostic.
        managed_refusal=(),
        detail="open one span and report the cost of a model call",
    ),
    "evaluation": PortCase(
        invoke=_evaluation_invoke,
        answered=_evaluation_answered,
        # The managed gate reaches model-quality-gate over HTTP, which is unreachable offline.
        managed_refusal=(Exception,),
        detail="score one golden dataset through the promotion authority",
    ),
}
