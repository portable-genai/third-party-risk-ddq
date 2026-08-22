"""The vendor due-diligence orchestrator: ports in, a deterministic assessment out (slices 2-7).

This is where the ports and the pure engines meet. It extracts evidence documents, normalises
DDQ answers (model, schema-validated), researches adverse media, computes financial status,
diffs the contract, scores inherent/residual risk, analyses gaps grounded in the reg KB, drafts
follow-ups and the memo (model narration only), then redacts and audits, routes the memo to Hrz7
(rule R8) and writes the register row. Every consequential number is produced by an engine;
with the generation port stubbed by the local adapter, the numbers are identical.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from pii_kit import redact

from ..ports.audit import AuditSinkPort
from ..ports.compliance import CompliancePort
from ..ports.contract_terms import ContractTermsPort
from ..ports.extraction import DocumentExtractionPort
from ..ports.generation import GenerationPort
from ..ports.register_store import RegisterStorePort
from ..ports.research import AdverseMediaPort
from ..ports.review_router import ReviewRouterPort
from .contract_diff import diff_contract
from .evidence_ledger import EvidenceLedger
from .financials import assess_financials
from .gap_engine import analyse_gaps
from .hitl import MemoReviewPolicy
from .kernel import AuditEvent, Citation, Decision, Severity, utcnow
from .models import TriageResult
from .pii import PII_PATTERNS
from .register_service import RegisterService
from .scoring_engine import ScoringPolicy, score_vendor
from .tprm_models import (
    CanonicalControl,
    ComplianceRequirement,
    DocumentRef,
    EvidenceItem,
    FinancialFigures,
    FinancialStatus,
    FollowUp,
    Gap,
    MediaFinding,
    RawDDQAnswer,
    RegisterEntry,
    VendorAssessment,
    VendorProfile,
)


class AssessmentService:
    """Run a whole vendor assessment deterministically and route its memo to human review."""

    def __init__(
        self,
        *,
        extraction: DocumentExtractionPort,
        research: AdverseMediaPort,
        contract_terms: ContractTermsPort,
        compliance: CompliancePort,
        generation: GenerationPort,
        register_store: RegisterStorePort,
        audit: AuditSinkPort,
        review_router: ReviewRouterPort,
        scoring_policy: ScoringPolicy | None = None,
    ) -> None:
        self._extraction = extraction
        self._research = research
        self._contract_terms = contract_terms
        self._compliance = compliance
        self._generation = generation
        self._register = RegisterService(register_store)
        self._audit = audit
        self._review_router = review_router
        self._policy = scoring_policy or ScoringPolicy()
        self._memo_policy = MemoReviewPolicy()

    def assess(
        self,
        profile: VendorProfile,
        documents: tuple[DocumentRef, ...],
        *,
        actor: str,
        tenant: str,
        as_of: date,
    ) -> VendorAssessment:
        ledger, ddq_answers, figures = self._ingest(documents)
        # The model normalises DDQ answers into schema-valid claims; unparseable ones are dropped
        # and resurface as unanswered-domain gaps. The claims drive coverage, never the score.
        claims = self._generation.normalise_ddq(ddq_answers)

        media = self._research.search(profile.name)
        financials: FinancialStatus | None = assess_financials(figures) if figures else None

        commitments = self._contract_terms.commitments(profile.name, tenant=tenant)
        mismatches = diff_contract(commitments, ledger)

        score = score_vendor(profile, ledger, media, financials, as_of=as_of, policy=self._policy)

        controls = tuple(CanonicalControl)
        requirements = self._compliance.requirements(controls, actor=actor)
        gaps = analyse_gaps(ledger, claims, mismatches, requirements, as_of=as_of)

        drafts = self._generation.draft_followups(gaps)
        follow_ups = tuple(
            FollowUp(gap_id=gid, question=draft.text)
            for draft in drafts
            for gid in draft.grounded_gap_ids
        )
        grounded_gap_ids = tuple(gap.gap_id for gap in gaps)
        memo = self._generation.draft_memo(
            profile.name, score.residual_band.value, grounded_gap_ids
        )

        citations = self._collect_citations(media, requirements, gaps)
        assessment = VendorAssessment(
            vendor=profile.name,
            as_of=as_of,
            inherent_band=score.inherent_band,
            residual_band=score.residual_band,
            inherent_factors=score.factors,
            residual_points=score.residual_points,
            hard_signals=score.hard_signals,
            gaps=gaps,
            follow_ups=follow_ups,
            memo=memo,
            requires_human_review=self._memo_policy.requires_review(
                score.residual_band, score.hard_signals
            ),
            citations=citations,
        )

        self._record(assessment, actor=actor)
        self._route(assessment, actor=actor, tenant=tenant)
        self._register.upsert(
            RegisterEntry(
                vendor=assessment.vendor,
                tenant=tenant,
                residual_band=assessment.residual_band,
                material=False,
                as_of=as_of,
                citations=citations,
            ),
            principal_tenant=tenant,
        )
        return assessment

    # ---------------------------------------------------------------- helpers

    def _ingest(
        self, documents: tuple[DocumentRef, ...]
    ) -> tuple[EvidenceLedger, tuple[RawDDQAnswer, ...], FinancialFigures | None]:
        items: list[EvidenceItem] = []
        answers: list[RawDDQAnswer] = []
        figures: FinancialFigures | None = None
        for document in documents:
            extracted = self._extraction.extract(document)
            items.extend(extracted.controls)
            answers.extend(extracted.ddq_answers)
            if extracted.figures is not None:
                figures = extracted.figures
        return EvidenceLedger(items=tuple(items)), tuple(answers), figures

    @staticmethod
    def _collect_citations(
        media: tuple[MediaFinding, ...],
        requirements: Mapping[CanonicalControl, ComplianceRequirement],
        gaps: tuple[Gap, ...],
    ) -> tuple[Citation, ...]:
        seen: set[str] = set()
        out: list[Citation] = []
        for finding in media:
            _add(out, seen, finding.citation)
        for gap in gaps:
            _add(out, seen, gap.citation)
        for req in requirements.values():
            _add(out, seen, req.citation)
        return tuple(out)

    def _record(self, assessment: VendorAssessment, *, actor: str) -> None:
        signals = "; ".join(assessment.hard_signals) or "none"
        summary = (
            f"{assessment.vendor}: inherent {assessment.inherent_band.value}, residual "
            f"{assessment.residual_band.value}; {len(assessment.gaps)} gaps; signals: {signals}"
        )
        self._audit.record(
            AuditEvent(
                action="assess",
                actor=actor,
                decision=Decision.ESCALATED,
                severity=assessment.residual_band,
                redacted_summary=redact(summary, PII_PATTERNS),
                citations=assessment.citations,
                timestamp=utcnow(),
            )
        )

    def _route(self, assessment: VendorAssessment, *, actor: str, tenant: str) -> str:
        envelope = self._envelope(assessment)
        return self._review_router.route(envelope, maker=actor, tenant=tenant)

    @staticmethod
    def _envelope(assessment: VendorAssessment) -> TriageResult:
        """Map the assessment onto the review envelope the R8 router and payload already handle."""
        return TriageResult(
            subject=assessment.vendor,
            severity=assessment.residual_band,
            decision=Decision.ESCALATED,
            summary=(
                f"Risk-acceptance memo for {assessment.vendor}: residual "
                f"{assessment.residual_band.value}"
            ),
            requires_human_review=assessment.requires_human_review,
            citations=assessment.citations,
        )


def _add(out: list[Citation], seen: set[str], citation: Citation) -> None:
    if citation.source_id in seen:
        return
    seen.add(citation.source_id)
    out.append(citation)


# Kept importable so callers can reference the band type without reaching into kernel directly.
ResidualBand = Severity
