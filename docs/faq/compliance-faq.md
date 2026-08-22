# Compliance FAQ

For compliance, model risk and the second line. The mapping table with a file reference on every
row is [`../../COMPLIANCE.md`](../../COMPLIANCE.md); this page answers the questions that come
back after reading it.

### Is the risk rating defensible in front of a regulator?

That is the reason it is pure code. Inherent risk is a weighted sum of four declared factors
(service criticality, data classification, jurisdiction, substitutability) against a frozen
`ScoringPolicy`; residual risk is those points reduced by control effectiveness that the evidence
ledger actually EVIDENCES, never by what a vendor asserted about itself
(`domain/scoring_engine.py`). Every factor is recorded on the result, so the same vendor and the
same documents always produce the same bands and the decision can be replayed years later from
the audit record. No model participates in it. Three properties matter for a review:

- **A hard signal cannot be argued away.** A sanctions-category adverse-media hit forces
  CRITICAL. An adverse SOC 2 opinion, an expired certificate, a going-concern failure or a
  critical financial ratio each raise the residual band by one.
- **Self-attestation earns no credit.** The DDQ claim path drives coverage and gap detection; the
  score reads tested evidence.
- **An unknown control identifier becomes a gap, not a guess.** The taxonomy packs map what they
  know and surface the rest as unmapped evidence.

The scoring policy shipped here is a REFERENCE, not your risk appetite: the weights, bands and
the `high_risk_jurisdictions` placeholder set are for your risk function to own.

### Who signs off a risk acceptance?

A human, always. `domain/hitl.py` sets `requires_review` UNCONDITIONALLY on the memo, because a
risk-acceptance decision is board-and-regulator-facing; the escalation floor only decides whether
it additionally goes to senior or risk-committee sign-off. `requires_human_review` and the call
to `ReviewRouterPort.route` are one act, not a flag plus an intention: the API, the CLI and the
agent tool all route in the same call that produced the result, and
`tests/unit/test_review_routing.py` asserts the routing rather than the flag. A CRITICAL band
demands two approvals. Under the managed profile the router REFUSES when no console is
configured, so a deployment cannot swallow an escalation silently.

### Where does the data live, and is residency enforced or just documented?

Enforced at deploy time. The region is chosen once (`asia-southeast1`) and shared by the runtime
and Terraform: `infra/terraform/variables.tf` validates the region against the residency
allowlist at plan, `org_policy.tf` pins `gcp.resourceLocations` to that region's location group,
and every regional resource (the CMEK key ring, the WORM log bucket, the Cloud Run service) is
created in it. `infra/terraform/production_edge.tftest.hcl` is the standing proof: its
`reject_region_outside_the_residency_allowlist` and `residency_defaults_are_in_country` runs fail
if the allowlist stops refusing or a resource drifts off region, and they run against a mocked
provider so they need no project and no credentials.

### What about key management and least privilege?

One REGIONAL CMEK key with a 90-day rotation, and an explicit key binding for EACH service agent
that encrypts under it, because CMEK does not cascade (`infra/terraform/kms.tf`). One serving
identity holding four roles, each traceable to a bound adapter, with `logging.logWriter` write
only so the process cannot read back the WORM trail it writes (`iam.tf`). Exportable
service-account keys are forbidden by org policy rather than merely avoided, and a key creation
raises an alert if one happens anyway (`org_policy.tf`, `monitoring.tf`).

### How long is the audit trail kept, and can it be edited?

180 days by default, and the variable refuses anything below 180. The Cloud Logging bucket is
LOCKED by default, which is irreversible: once applied, retention cannot be reduced and the
bucket cannot be deleted for the full window, not even with project-owner rights. Confirm
`retention_days` before the first apply. DATA_READ audit logging is enabled too, so a read of the
evidence is itself recorded: a trail that records who was decided about but not who read the
decision is half a trail.

Offline the same guarantee is earned differently: the log is hash-chained AND externally
anchored, because a truncated tail leaves a shorter chain that verifies perfectly. The retention
schedule and the legal basis for the trail are adopter-owned.

### What personal data does this system process?

By design, very little: it reasons over vendor evidence documents, control observations,
financial figures and contract clauses rather than customer records. Named individuals can
nonetheless appear in a DDQ answer, an adverse-media finding or an audit report, so whatever does
appear is masked before every boundary (the audit write, the outbound review payload, and any
tool result that could enter a model's context), with the jurisdiction rows and their ORDER
chosen in `domain/pii.py`. The `pii_safety` metric holds this at `>= 0.99`, scored two ways, and
is proved able to go red.

### What model-risk evidence exists?

[`../model-card.md`](../model-card.md), and its headline finding is that **no model runs here
today**. There is a `GenerationPort` seam, the offline adapter is a deterministic rule-based
stub, and the managed adapter raises without ever selecting a model id or building a prompt. Two
consequences for a model-risk review. First, nothing to review yet: the offline eval
(`eval/run_eval.py --mode smoke`) scores `scoring_accuracy`, `extraction_fidelity`, `gap_recall`,
`review_safety` and `pii_safety` on the deterministic pipeline on every change, and every one is
proved able to go red. Second, the controls that MUST land before a model is bound are named in
the card: runtime output validation (which does not exist yet, so a draft's gap ids and a memo's
figures are not cross-checked against the engine's own), a pinned model id and version, a token
budget, a rate limit and a kill switch, a live-model eval run registered with Hrz4, and
prompt-injection screening through Hrz1. Until those close, the deterministic path is what should
be relied on.

### Which regulations does this claim to satisfy?

None, on your behalf. The mapping in `COMPLIANCE.md` is to the CATALOG's own principles (P-01 to
P-13) and platform rules (R1 to R8). The crosswalk from those to MAS TRM, CPS 234, CPS 230, HKMA
or PDPA control ids, and the judgement that a control is SUFFICIENT for a regulation, is
explicitly adopter-owned: it depends on your risk appetite, your regulator and your existing
control library. No row in that document should be quoted as regulatory assurance, and the
second-line review of the deterministic policy in `domain/` is bank-owned logic rather than a
vendor default to inherit unexamined.

### What is still open at go-live?

The `Partial` and `TODO (repo owner)` rows in `COMPLIANCE.md`, each of which names exactly what
is missing. The ones that need a risk acceptance if you go live without them: the ten
construction-only managed operations in `src/tprm_ddq/managed_readiness.py` (which the container
preflight and the Terraform serving-edge check currently refuse to let you deploy past), rule R1
(the Hrz1 guardrail binding, before any model), rule R5 and P-08 (the Hrz4 metric bundle), P-10
(timeouts, circuit breaker and a documented kill switch), the object-level tenant authorisation
noted in the cross-cutting table, and P-01's private-egress rule, which depends on your own
network rather than on this repo.
