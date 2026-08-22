"""The triage path opens ONE span, and that span carries no content.

A trace backend is not the WORM audit trail. It has no redaction stage, no retention policy
written against a regulator's requirement, and a far wider read audience than the audit
store. So the value of tracing the triage path depends entirely on the span carrying
structural attributes only: which action, whose. A case's free text, its subject or a
planted identifier reaching a span has left the boundary the service's ``redact`` call
exists to hold, and it has left it silently.

The content case drives the case whose text carries a planted NRIC, so the check runs
against input that would actually leak if any attribute were content-shaped.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from tprm_ddq.config import Settings, build_container
from tprm_ddq.domain.models import TriageInput
from tprm_ddq.domain.triage_service import TriageService

from tests.fixtures import sample_cases

#: Every attribute key the triage span is allowed to carry. A verdict that started explaining
#: itself on the span (a severity, a subject, a snippet) would widen this set, which is the
#: point of asserting on the set rather than on the individual keys.
_TRIAGE_KEYS = {"action", "actor"}


class _RecordingTracer:
    """Captures every span name and attribute so the test can inspect what was emitted."""

    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, str]]] = []

    @contextmanager
    def span(self, name: str, **attributes: str) -> Iterator[None]:
        self.spans.append((name, dict(attributes)))
        yield

    def record_token_usage(self, usage: object, model: str) -> None:
        return None


def _triage(case: TriageInput) -> _RecordingTracer:
    tracer = _RecordingTracer()
    container = build_container(Settings(profile="local", audit_path=":memory:"))
    service = TriageService(container.audit, tracer=tracer)  # type: ignore[arg-type]
    service.triage(case, actor=sample_cases.ACTOR)
    return tracer


def _emitted(tracer: _RecordingTracer) -> str:
    """Every attribute KEY and VALUE that was emitted, as one searchable blob."""
    parts: list[str] = []
    for name, attributes in tracer.spans:
        parts.append(name)
        parts.extend(attributes)
        parts.extend(attributes.values())
    return " ".join(parts)


def test_triaging_a_case_opens_exactly_one_named_span() -> None:
    tracer = _triage(sample_cases.ROUTINE_CASE)
    assert [name for name, _ in tracer.spans] == ["tprm_ddq.triage"]


def test_the_span_carries_the_structural_attributes_an_operator_needs() -> None:
    """Enough to answer "whose triage is slow", and nothing more."""
    _, attributes = _triage(sample_cases.ROUTINE_CASE).spans[0]
    assert attributes["action"] == "triage"
    assert attributes["actor"] == sample_cases.ACTOR


@pytest.mark.parametrize(
    "case",
    [sample_cases.ROUTINE_CASE, sample_cases.ESCALATING_CASE, sample_cases.PII_CASE],
    ids=["routine", "escalating", "pii"],
)
def test_the_attribute_set_is_a_fixed_allowlist_whatever_the_verdict(case: TriageInput) -> None:
    """An escalating case must not start attaching its band, or its text, to the span."""
    tracer = _triage(case)
    for _, attributes in tracer.spans:
        assert set(attributes) == _TRIAGE_KEYS, (
            "a new span attribute appeared; confirm it is structural, then widen "
            "_TRIAGE_KEYS here deliberately"
        )


def test_no_span_attribute_carries_case_content_or_the_planted_identifier() -> None:
    """The case used here has an NRIC planted in its free text, so a leak would show."""
    tracer = _triage(sample_cases.PII_CASE)
    emitted = _emitted(tracer).lower()
    forbidden = (
        sample_cases.PLANTED_NRIC,
        sample_cases.PII_CASE.text,
        sample_cases.PII_CASE.subject,
        "ops@gamma.example",
        "urgent breach",
    )
    for literal in forbidden:
        assert literal, "an empty needle would pass this test for the wrong reason"
        assert literal.lower() not in emitted, f"a span attribute carried {literal!r}"


def test_every_emitted_attribute_value_is_a_string_the_port_declares() -> None:
    """``span(name, **attributes: str)``: a non-string would serialise however the SDK felt."""
    tracer = _triage(sample_cases.ESCALATING_CASE)
    values = [v for _, attributes in tracer.spans for v in attributes.values()]
    assert values
    assert all(isinstance(value, str) for value in values)
