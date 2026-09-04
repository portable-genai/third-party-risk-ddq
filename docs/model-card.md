# Model card: Third-Party Risk Due-Diligence Agent (`third-party-risk-ddq`)

This is a STARTER model card. It records the model boundary as built and the controls that must
be completed before a managed deployment. The deterministic engines are the system of record; a
model is a bounded, replaceable component.

**Read this first: no model runs in this repo today.** There is a model-shaped seam
(`ports/generation.py`), but the only adapter that answers is a deterministic rule-based stub,
and the managed adapter raises rather than calling anything. Every number a vendor assessment
carries is produced by pure stdlib code either way.

## What the model does, and does not do

- **Does** (once an adopter binds a real one): three narration-shaped jobs behind
  `GenerationPort`. `normalise_ddq` turns free-text DDQ answers into control-keyed `DDQClaim`
  values, `draft_followups` phrases one follow-up question per engine-identified gap, and
  `draft_memo` phrases the risk-acceptance memo for a residual band the engine already computed.
- **Does NOT**: produce any band, score, gap, mismatch, financial status or escalation. Inherent
  and residual risk (`domain/scoring_engine.py`), the cited gap set (`domain/gap_engine.py`),
  liquidity, leverage and going concern (`domain/financials.py`), the contract-versus-evidence
  diff (`domain/contract_diff.py`) and the human-review decision (`domain/hitl.py`) are pure
  stdlib over declared facts. The DDQ claims a model normalises drive coverage only; the score
  reads the tested evidence in the ledger, never the self-attested effectiveness. A hard signal
  (a sanctions-category media hit, an adverse SOC 2 opinion, an expired certificate, a
  going-concern failure, a critical financial ratio) raises the band and cannot be softened by
  narrative.

## Adapters and profiles

| Profile | Generation adapter | Behaviour |
|---|---|---|
| `local` | `adapters/local/generation.py` | Deterministic rule-based stub: a keyword rule reads a self-attested effectiveness from each DDQ answer, one follow-up is assembled from the gap's own fields, and the memo restates the engine's residual band and open gap ids. SDK-free, no model, no network. |
| `gcp` | `adapters/gcp/generation.py` | **Not wired.** All three methods perform the lazy `from google import genai` import and then raise `RuntimeError("Gemini generation is not configured for the gcp profile")`. No prompt is built, no request is sent, no model id is selected. |
| `onprem` | `adapters/onprem/generation.py` | Fail-fast placeholder: raises, naming the client-hosted model gateway to bind. |

Two other ports would reach an ML service under a wired `gcp` profile, and neither is wired
either: `DocumentExtractionPort` (`adapters/gcp/extraction.py`, Document AI) and
`AdverseMediaPort` (`adapters/gcp/research.py`, a Google Search grounded sub-agent that isolates
web egress in one place). Both raise today. Offline, extraction is a real deterministic parser
over a fixture evidence format (so extraction fidelity is measurable against golden labels) and
research is a fictional severity-ordered fixture corpus.

This is declared in code rather than left to be discovered.
`src/tprm_ddq/managed_readiness.py` lists all ten construction-only managed operations, the API
preflight and the container command refuse to start a `gcp` process whose bindings select one of
them, and `infra/terraform/managed_readiness.tf` refuses to authorise the serving edge for the
same reason. So the managed model path is not merely unfinished, it is fail-closed.

## Boundary as built

- A model is reachable through exactly one port, `ports/generation.py`, with three methods. There
  is no second model seam in the request path.
- The stub deliberately produces only prose and schema-shaped claims, never a number. With it
  bound, every consequential field of a `VendorAssessment` is byte-identical run to run, which is
  the property `eval/run_eval.py` scores.
- Personal data is masked before the audit write (`domain/triage_service.py`,
  `domain/assessment_service.py`), before a review payload leaves the process
  (`adapters/_review_payload.py`, against EVERY jurisdiction's rows because the console is a
  shared sink), and before a tool result can enter a model's context (`agent/tools.py`).
- A risk-acceptance memo is unconditionally human (`domain/hitl.py`: `requires_review` is always
  True) and is routed to `human-review-console` in the same call that produced it (rule R8); nothing auto-executes.

## Remaining controls (TODO, repo owner)

- **Output validation does not exist yet, and it is the first thing to add.** The port docstrings
  describe model output as schema-validated, but that is a TYPE guarantee from the frozen
  dataclasses, not a runtime check. Specifically: `assessment_service.assess` builds `FollowUp`
  rows straight from each `LlmDraft.grounded_gap_ids` without checking that those ids are in the
  gap set the engine just produced, and the memo string is stored without checking that every
  figure it names is one the engine computed. With the local stub both are grounded by
  construction; with a real model bound they are not. Add the membership check and a figure
  allowlist, discard a failing reply rather than repairing it, and fall back to the deterministic
  draft.
- **Model id, version and region** (P-07, P-11): no model id is selected anywhere in the
  generation adapter. `adapters/gcp/evaluation.py` and `eval/run_eval.py` record
  `gemini-3.5-flash` as the model a promotion verdict is keyed to, which is a placeholder that
  the generation path does not honour because it makes no call. Pin the exact model and version,
  confirm it is served in your deployment region (Gemini model ids are regional and an
  unavailable one fails at call time rather than at boot), and record it here.
- **Budget, rate limit and a kill switch** (P-10, P-11): there is no per-tenant token budget, no
  request rate limit, and no switch that forces deterministic-only operation. Today the stub IS
  the deterministic-only mode, so the switch is a binding change rather than an operator action.
- **Evaluation of the live model**: the offline eval scores the deterministic pipeline with the
  stub bound. Add a managed-profile run, registered with the `model-quality-gate` promotion gate (P-08, rule R5),
  that scores the memo's and the follow-ups' groundedness against the same golden vendors with a
  real model bound.
- **Prompt-injection screening** (rule R1): the `agent-guardrail-gateway` is not bound, and this
  vertical's inputs are unusually hostile. A DDQ answer, an evidence document and an
  adverse-media snippet are all written by, or about, the party being assessed. Screen every one
  of them before it reaches a model, and fail closed to deterministic-only when the screen is
  unavailable.
- **Reasoning trace**: `COMPLIANCE.md` P-07 records that a model's reasoning trace should be
  audited alongside its output. Today the audit record carries the redacted assessment summary
  and its citations, not a prompt and reply pair.

Until these are complete the system is safe to run offline (deterministic engines plus the
rule-based stub) and no managed model path is production-cleared.
