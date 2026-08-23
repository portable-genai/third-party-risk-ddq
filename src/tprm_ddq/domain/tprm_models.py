"""Vendor due-diligence artifacts: the types the deterministic engines reason over.

The vertical this repo actually ships. ``kernel.py`` holds the vertical-neutral machinery
(Citation, Severity, Decision, AuditEvent); everything here is specific to third-party risk:
the canonical control set every evidence source maps onto, the evidence ledger's item shape,
the DDQ claim the model normalises free text into, the adverse-media and financial findings,
the contract commitments and their mismatches, the risk-scoring inputs and result, and the
cited gaps and follow-up questions.

Every consequential number on :class:`VendorAssessment` is produced by a pure engine
(``scoring_engine``, ``gap_engine``, ``financials``, ``contract_diff``); the model only
narrates. All of it is stdlib and frozen, so an assessment replays byte-identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from hex_service_kit.enums import LenientStrEnum

from .kernel import Citation, Severity, redacted_citations


class CanonicalControl(LenientStrEnum):
    """The one control taxonomy every evidence framework is mapped onto.

    SOC 2 Trust Services Criteria, ISO 27001 Annex A and SIG/CAIQ domains all fold into this
    canonical set, so the evidence ledger is keyed by a control the engine understands rather
    than by whichever framework a given report happened to use.
    """

    ACCESS_CONTROL = "access_control"
    ENCRYPTION = "encryption"
    INCIDENT_RESPONSE = "incident_response"
    BUSINESS_CONTINUITY = "business_continuity"
    CHANGE_MANAGEMENT = "change_management"
    VENDOR_MANAGEMENT = "vendor_management"
    DATA_GOVERNANCE = "data_governance"
    LOGGING_MONITORING = "logging_monitoring"
    RISK_MANAGEMENT = "risk_management"
    HR_SECURITY = "hr_security"


class ControlEffectiveness(LenientStrEnum):
    """How well an evidenced control operates. Worst-to-best order in ``EFFECTIVENESS_RANK``."""

    ABSENT = "absent"
    INEFFECTIVE = "ineffective"
    PARTIAL = "partial"
    EFFECTIVE = "effective"
    UNTESTED = "untested"


class EvidenceKind(LenientStrEnum):
    """Which source an evidence item came from (drives the mandatory-evidence gap check)."""

    DDQ_ANSWER = "ddq_answer"
    SOC2 = "soc2"
    ISO_CERT = "iso_cert"
    FINANCIAL_STATEMENT = "financial_statement"
    ADVERSE_MEDIA = "adverse_media"
    CONTRACT = "contract"


class MediaCategory(LenientStrEnum):
    """Adverse-media category. ``SANCTIONS`` is a hard signal the model can never soften."""

    SANCTIONS = "sanctions"
    FINANCIAL_CRIME = "financial_crime"
    DATA_BREACH = "data_breach"
    LITIGATION = "litigation"
    GOVERNANCE = "governance"
    NONE = "none"


class DataClassification(LenientStrEnum):
    """The most sensitive data class the vendor processes (an inherent-risk factor)."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class Substitutability(LenientStrEnum):
    """How readily the vendor could be replaced (an inherent-risk factor)."""

    COMMODITY = "commodity"
    MODERATE = "moderate"
    SPECIALISED = "specialised"
    SOLE_SOURCE = "sole_source"


#: Worst-to-best ordering used by the deterministic scoring engine. A frozen module constant so
#: the number a control contributes is policy, not an accident of enum declaration order.
EFFECTIVENESS_RANK: dict[ControlEffectiveness, int] = {
    ControlEffectiveness.ABSENT: 0,
    ControlEffectiveness.INEFFECTIVE: 1,
    ControlEffectiveness.PARTIAL: 2,
    ControlEffectiveness.UNTESTED: 2,
    ControlEffectiveness.EFFECTIVE: 4,
}

SEVERITY_RANK: dict[Severity, int] = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


@dataclass(frozen=True, slots=True)
class DocumentRef:
    """A document handed to the extraction port: an id, its bytes/text and its media type."""

    doc_id: str
    content: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class RawDDQAnswer:
    """A free-text DDQ answer parsed from a document, before the model normalises it.

    ``control`` is the extractor's candidate mapping (may be ``None`` when the domain is
    ambiguous); the generation port turns the answer into a schema-valid :class:`DDQClaim`, and
    an answer it cannot parse is recorded as a gap rather than guessed.
    """

    control: CanonicalControl | None
    answer_text: str
    citation: Citation


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    """What the extraction port returns: full text plus deterministically parsed structure.

    ``controls`` are tested control observations (from a SOC 2 / ISO report's structured layout)
    that feed the evidence ledger deterministically; ``ddq_answers`` are free-text answers for
    the model to normalise; ``figures`` are financial figures when the document is a statement.
    """

    doc_id: str
    mime_type: str
    full_text: str
    controls: tuple[EvidenceItem, ...] = field(default_factory=tuple)
    ddq_answers: tuple[RawDDQAnswer, ...] = field(default_factory=tuple)
    figures: FinancialFigures | None = None


@dataclass(frozen=True, slots=True)
class VendorProfile:
    """The inherent-risk inputs: what the vendor does and how exposed the firm is to it."""

    name: str
    service_criticality: Severity
    data_classification: DataClassification
    jurisdiction: str
    substitutability: Substitutability


@dataclass(frozen=True, slots=True)
class DDQClaim:
    """A schema-validated claim the model normalised from one free-text DDQ answer.

    The model produces the ``control`` mapping and the ``effectiveness`` reading; it may never
    produce a risk band. An answer that cannot be parsed becomes a gap, never a guessed claim,
    so a claim always carries the citation to the span it came from.
    """

    control: CanonicalControl
    effectiveness: ControlEffectiveness
    answer_text: str
    citation: Citation


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One control observation in the ledger, from any framework, already mapped to canonical."""

    control: CanonicalControl
    kind: EvidenceKind
    effectiveness: ControlEffectiveness
    as_of: date
    citation: Citation
    #: A SOC 2 report with a qualified/adverse opinion, or an expired certificate: hard signals.
    adverse_opinion: bool = False
    expired: bool = False


@dataclass(frozen=True, slots=True)
class MediaFinding:
    """One adverse-media hit, severity-ordered. A SANCTIONS category is a hard band-raiser."""

    subject: str
    category: MediaCategory
    severity: Severity
    headline: str
    citation: Citation


@dataclass(frozen=True, slots=True)
class FinancialFigures:
    """Figures the model EXTRACTED from a financial statement. The engine derives status."""

    current_assets: float
    current_liabilities: float
    total_debt: float
    total_equity: float
    going_concern_flag: bool
    citation: Citation


@dataclass(frozen=True, slots=True)
class FinancialStatus:
    """The DETERMINISTIC financial reading. Computed by ``financials``; prose cannot override it."""

    current_ratio: float
    debt_to_equity: float
    liquidity: Severity
    leverage: Severity
    going_concern: bool
    citation: Citation


@dataclass(frozen=True, slots=True)
class ContractCommitment:
    """One contractual commitment from Rgc12, keyed to the canonical control it evidences."""

    control: CanonicalControl
    term: str
    present: bool
    citation: Citation


@dataclass(frozen=True, slots=True)
class ContractMismatch:
    """A deterministic contradiction between a contract commitment and the evidence ledger."""

    control: CanonicalControl
    description: str
    clause_citation: Citation
    evidence_citation: Citation


class GapKind(LenientStrEnum):
    """Why a gap was raised (drives ranking and the follow-up wording the model may draft)."""

    MISSING_EVIDENCE = "missing_evidence"
    STALE_EVIDENCE = "stale_evidence"
    CONTRACT_MISMATCH = "contract_mismatch"
    UNANSWERED_DOMAIN = "unanswered_domain"
    WEAK_CONTROL = "weak_control"


@dataclass(frozen=True, slots=True)
class Gap:
    """A cited gap. ``rule_ref`` grounds it in an outsourcing-rule expectation from Rsk1."""

    gap_id: str
    kind: GapKind
    control: CanonicalControl
    severity: Severity
    description: str
    rule_ref: str
    citation: Citation


@dataclass(frozen=True, slots=True)
class ComplianceRequirement:
    """An outsourcing-rule expectation for a control, grounded in Rsk1's reg KB.

    The engine never invents regulatory text: a gap cites the ``rule_ref`` and ``citation``
    fetched from the compliance port, so the follow-up and memo quote a real requirement.
    """

    control: CanonicalControl
    rule_ref: str
    text: str
    citation: Citation


@dataclass(frozen=True, slots=True)
class FollowUp:
    """A model-drafted follow-up question, tied to the engine gap it addresses."""

    gap_id: str
    question: str


@dataclass(frozen=True, slots=True)
class FactorScore:
    """One weighted factor's contribution, kept so the panel can show the arithmetic."""

    name: str
    band: Severity
    weight: int
    points: int


@dataclass(frozen=True, slots=True)
class RegisterEntry:
    """One row of the Outsourcing and Material-Arrangements Register (slice 7).

    Tenant-scoped and materiality-flagged deterministically from policy thresholds. Rgc9 reads
    this over A2A as data. ``material`` is computed by the register store from the residual band
    and the profile, never asserted by a caller.

    Construction MASKS the citations, for the same reason :class:`~.kernel.AuditEvent` does and
    with the same call: the register is the audit record's sibling sink, not a lesser one. It is
    long-lived, tenant-scoped and read by Rgc9 as data, and an extraction citation carries a
    snippet cut straight out of an uploaded document, so raw client text reached it under a
    structural-looking name. ``AssessmentService.assess`` hands the SAME citation tuple to the
    audit writer and to this row; masking only the first left the identifier one sink away.
    Redaction is idempotent, so a caller that already masked loses nothing, and a writer added
    later cannot leak by forgetting.

    ``vendor`` and ``tenant`` are NOT masked. They are the identity of the row and the pair the
    store authorises on: masking them would erase the register's subject or break tenant
    isolation. Same reasoning as ``AuditEvent.actor``, and the reason a leak scan runs over the
    content fields rather than over a whole row.
    """

    vendor: str
    tenant: str
    residual_band: Severity
    material: bool
    as_of: date
    citations: tuple[Citation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "citations", redacted_citations(tuple(self.citations)))


@dataclass(frozen=True, slots=True)
class LlmDraft:
    """A schema-validated narration returned by the generation port (prose only, no numbers)."""

    text: str
    grounded_gap_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class VendorAssessment:
    """The whole assessment: inherent/residual bands, the arithmetic, gaps, follow-ups, memo.

    Every band and number here comes from a pure engine. ``requires_human_review`` is always
    True (a risk-acceptance decision is consequential) and the assessment routes to Hrz7.
    """

    vendor: str
    as_of: date
    inherent_band: Severity
    residual_band: Severity
    inherent_factors: tuple[FactorScore, ...]
    residual_points: int
    hard_signals: tuple[str, ...]
    gaps: tuple[Gap, ...]
    follow_ups: tuple[FollowUp, ...]
    memo: str
    requires_human_review: bool
    citations: tuple[Citation, ...] = field(default_factory=tuple)
