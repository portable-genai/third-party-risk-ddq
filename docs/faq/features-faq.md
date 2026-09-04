# Features FAQ

For a product owner, a risk lead or a delivery manager deciding what this system does, what it
refuses to do, and where its responsibility ends.

### What does it actually do?

Given a vendor profile and a set of evidence documents, it produces a cited due-diligence
assessment in seven deterministic steps and three narrated ones
(`domain/assessment_service.py` is the orchestrator):

1. **Extraction** (`DocumentExtractionPort`): parse each evidence document into control
   observations, free-text DDQ answers and financial figures, mapping every framework identifier
   onto the canonical control set.
2. **Evidence ledger** (`domain/evidence_ledger.py`): index every observation by the canonical
   control it evidences, and how strongly.
3. **Adverse media** (`AdverseMediaPort`): severity-ordered findings, each carrying a media
   citation.
4. **Financial health** (`domain/financials.py`): liquidity, leverage and going-concern status
   computed from the extracted figures against a frozen `FinancialPolicy`.
5. **Contract diff** (`domain/contract_diff.py`): each contractual commitment against what the
   ledger actually evidences, every mismatch citing BOTH the clause and the contradicting
   evidence item.
6. **Risk scoring** (`domain/scoring_engine.py`): inherent risk as a weighted sum of criticality,
   data classification, jurisdiction and substitutability; residual risk as those points reduced
   by evidenced control effectiveness. Hard signals raise the band.
7. **Cited gap analysis** (`domain/gap_engine.py`): missing mandatory evidence, stale reports,
   contract mismatches, unanswered DDQ domains and tested-weak controls, each mapped to the
   outsourcing-rule expectation it offends.

The three narrated steps run through `GenerationPort`: normalising DDQ answers into
control-keyed claims, phrasing one follow-up question per gap, and phrasing the risk-acceptance
memo. They compute nothing. The assessment is then redacted, audited, routed to `human-review-console` and written
to the outsourcing register.

### What is deterministic, and what does the model write?

Everything consequential is deterministic, and today **nothing is model-written at all**: the
only `GenerationPort` adapter that answers is a rule-based stub, and the managed adapter raises.
Every band, score, gap, mismatch and escalation is pure stdlib over declared facts, so the same
vendor profile and the same documents always produce the same assessment. The DDQ claims a model
normalises drive coverage only; the score reads the tested evidence in the ledger, never the
self-attested effectiveness. See [`../model-card.md`](../model-card.md), which also names the
output-validation control an adopter must add before binding a real model.

### What will it refuse to do?

- **It will not let narrative soften a hard signal.** A sanctions-category media hit forces
  CRITICAL. An adverse SOC 2 opinion, an expired certificate, a going-concern failure or a
  critical financial ratio each raise the residual band by one, whatever the prose says.
- **It will not guess a control.** A framework identifier the taxonomy packs do not know maps to
  nothing and is surfaced as an unmapped-evidence gap rather than mapped to a nearby control.
- **It will not invent regulatory text.** A control with no requirement fetched from `compliance-advisory` still
  yields a gap, cited to the evidence, with an explicit "no rule text available" reference.
- **It will not auto-accept risk.** `domain/hitl.py` sets `requires_review` unconditionally on
  the memo, and a consequential result is ROUTED to the `human-review-console` in the same call that
  produced it (rule R8), on every surface.
- **It will not answer across tenants.** A register read for another tenant is a 403 from the
  domain (`domain/register_service.py`), never a silent 404.
- **It will not answer without provenance.** Every result carries a `Citation`.

### Which surfaces expose it, and what does each one drive?

Be precise here, because the two domain paths are not equally exposed:

- The **triage path** (`domain/triage_service.py`, the deterministic severity band plus soft
  escalation) is what the FastAPI app (`POST /v1/triage`), the argparse CLI (`tprm_ddq triage`),
  the agent tools (`triage_case`, `verify_audit_trail`, advertised on the A2A card at
  `/.well-known/agent-card.json`), the embeddable `ui/` micro-frontend and the scripted demo all
  drive. Each routes escalations in the same call, so rule R8 does not hold on four surfaces out
  of five.
- The **full vendor assessment** (`domain/assessment_service.py`, steps 1 to 7 above) is driven
  today by the eval harness and its unit tests. It has no HTTP route, CLI subcommand or agent
  tool yet. Exposing it is vertical-slice work an adopter picks up, and it inherits the same
  identity, redaction and R8 routing rules when it does.

### What does this repo own, and what does it integrate?

| Concern | Owner | How this repo touches it |
|---|---|---|
| The vendor risk score, gap set and contract diff | **this repo (`third-party-risk-ddq`)** | the deterministic engines in `domain/`. Nothing else in the catalog computes them. |
| The Outsourcing and Material-Arrangements Register | **this repo (`third-party-risk-ddq`)** | written over `RegisterStorePort` with tenant authorisation in the domain. `operational-resilience-mapping` consumes it over A2A for reporting; this repo does not render that reporting. |
| Outsourcing-rule text and its citation | `compliance-advisory` | read over `CompliancePort`. This repo decides which gaps exist; it never authors regulatory text. |
| The vendor's contractual commitments | `contract-obligation-extraction` contract-obligation register | read over `ContractTermsPort`. `contract-obligation-extraction` is unshipped in this workspace, so the offline fixture adapter freezes the contract shape and a contract test pins it. |
| Agent discovery and entitlements | `agent-registry` | this agent publishes a card; the registry owns discovery. |
| Model and agent promotion | `model-quality-gate` AI quality and model risk | `eval/run_eval.py --mode gate` asks `model-quality-gate` (`TPRM_DDQ_QUALITY_URL`); the offline smoke mode never promotes. |
| Traces and the immutable audit sink | `agent-observability` agent observability | `AuditSinkPort` and `ObservabilityTracerPort`; the managed tracer exports OTLP to the `agent-observability` collector when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. |
| Human review and maker-checker | `human-review-console` human review console | `ReviewRouterPort` over the shared `review-kit` (`HUMAN_REVIEW_URL`). This repo produces escalations; it does not render a queue. |
| Prompt-injection defence and output filtering | `agent-guardrail-gateway` agent guardrail gateway | **not wired today.** It becomes mandatory the moment untrusted free text (a vendor-written DDQ answer, an uploaded document, a media snippet) reaches a live model (rule R1). |
| Grounded retrieval over an enterprise corpus | `enterprise-knowledge-base` | not wired today. `compliance-advisory` supplies the rule text this vertical needs; a general corpus is not in the request path. |

### Can I demo it without a cloud project?

Yes, and the demo is code rather than a deck. `make demo` runs a presenter-paced walkthrough over
eight steps (opened, routine, escalation, redaction, review queue, audit, tamper, portability) on
its own loopback server; `make demo-selftest` runs the same arc headless and asserts every
narrated claim, so a claim that stops being true fails a build rather than a meeting;
`make demo-static` renders the same audit-first panels to static HTML for screenshots.

### What is not built yet?

The honest list is [`../practices-audit.md`](../practices-audit.md) and the `TODO (repo owner)`
rows in [`../../COMPLIANCE.md`](../../COMPLIANCE.md). The three that matter most for a production
decision: the managed adapter family is construction-only (ten operations are listed in
`src/tprm_ddq/managed_readiness.py` and both the container preflight and the Terraform serving
edge refuse while they are), the full assessment pipeline has no serving surface yet, and the
`model-quality-gate` metric bundle is not registered so `--mode gate` has no authority to ask.
