# Adopting this repo as your base

This repository (`third-party-risk-ddq`, the Third-Party Risk Due-Diligence Agent) is a **common base** that a bank
or other regulated institution forks to build its own **vendor due-diligence engine**: a service
that reads a vendor's evidence documents, normalises the DDQ answers into a control-keyed
evidence ledger, scores inherent and residual risk, diffs the contract against what the evidence
actually shows, analyses cited gaps against outsourcing-rule expectations, drafts a
risk-acceptance memo and routes it to a human. It ships a reusable hexagonal core (a pure-stdlib
domain, typed ports, three swappable adapter profiles, a green offline gate) plus a fully worked
SOC 2 / ISO 27001 / SIG-CAIQ vertical you can keep, retune, or replace with your own control
taxonomy.

This guide is the step-by-step for making it yours. It has two halves: a **mechanical rebrand**
(one script) and the **human decisions** the script cannot make for you.

> Related reading: [`ARCHITECTURE.md`](../ARCHITECTURE.md) (the port table and topology),
> [`CONTRIBUTING.md`](../CONTRIBUTING.md) (adding an adapter, adding a port), the
> [`faq/`](faq/) directory, [`model-card.md`](model-card.md) (the model boundary),
> [`practices-audit.md`](practices-audit.md) (the per-check verdict).

---

## 1. What you keep vs what you rewrite

The core is hexagonal, and the boundary between reusable machinery and the due-diligence vertical
is a physical module split with an enforced dependency direction (practices-audit check A7).
`domain/kernel.py` owns the vertical-neutral contracts and imports nothing from the vertical, so
you can import it without loading a line of third-party-risk logic; `domain/tprm_models.py` holds
the `third-party-risk-ddq` artifacts and `domain/models.py` holds this service's request and result types.

| Layer | Where | For a new vertical |
|---|---|---|
| **Vertical-neutral machinery** | `domain/kernel.py` (`Citation`, `AuditEvent`, `Severity`, `Decision`, `utcnow`), `domain/errors.py`, every Protocol in `ports/`, the container wiring in `config.py` | keep untouched |
| **Policy (your numbers and sets)** | `ScoringPolicy` in `domain/scoring_engine.py` (the four inherent weights, the data and substitutability bands, the high-risk jurisdiction set, the inherent thresholds, the credited controls), `FinancialPolicy` in `domain/financials.py`, the `MemoReviewPolicy` escalation floor in `domain/hitl.py`, `MANDATORY_CONTROLS` and the framework packs in `domain/control_taxonomy.py`, the jurisdiction rows in `domain/pii.py`, the metric thresholds in `eval/run_eval.py` | change deliberately (see section 4) |
| **Vertical (the artifacts themselves)** | the `third-party-risk-ddq` models in `domain/tprm_models.py` (`CanonicalControl`, `EvidenceItem`, `DDQClaim`, `MediaFinding`, `ContractCommitment`, `Gap`, `VendorAssessment`, `RegisterEntry`), the engines (`scoring_engine.py`, `gap_engine.py`, `financials.py`, `contract_diff.py`, `evidence_ledger.py`), the orchestrators (`assessment_service.py`, `register_service.py`, `triage_service.py`), the local fixture corpora and the eval golden sets | rewrite for your vertical |

If your product is another *evidence-in, cited-verdict-out* gate, most of the hexagon, the three
profiles, the deterministic-scoring pattern, the eval gate and the `human-review-console` review routing transfer
directly; you replace the control taxonomy and the evidence sources, and retune the policy
dataclasses.

## 2. Core-vs-adopter-owned files (so upstream merges stay mechanical)

Upstream keeps evolving these; avoid diverging from them so you can pull fixes cleanly:

- **Upstream-owned** (take our changes): the vertical-neutral machinery listed above, `ports/`,
  `tests/contract/`, the eval harness mechanics (`eval/run_eval.py`), the CI workflows, the
  hexagon wiring (`config.py` `Container`) and the deploy stack in `infra/terraform/`.
- **Adopter-owned** (yours; expect to edit): `config/settings.yaml` *values*, the policy
  dataclasses named above, the local fixture corpora and the golden eval datasets,
  `adapters/onprem/*`, UI theming and branding, `infra/terraform/terraform.tfvars`, and the
  regulator crosswalk section of `COMPLIANCE.md`.

Track upstream via git tags; rebase your adopter-owned changes onto each release rather than
merging `main` continuously.

## 3. The mechanical rebrand (one script)

`scripts/rename_fork.py` rewrites the package name (`tprm_ddq`, which is also the console
script), the `TPRM_DDQ_` env prefix (including the bare `TPRM_DDQ` that
`infra/terraform/render.tf.json` carries as `render_env_prefix`, so Terraform sets the same
variable names on the Cloud Run service), the cloud resource stem (`rgc8-svc`, the Terraform
`name_prefix`) and the distribution / git id in one pass. Preview first, then apply:

```bash
# Preview (writes nothing):
python scripts/rename_fork.py --package acme_tprm_ddq --env-prefix ACME \
    --resource acme-tprm --dry-run

# Apply:
python scripts/rename_fork.py --package acme_tprm_ddq --env-prefix ACME \
    --resource acme-tprm --yes

# Then recreate the environment (the distribution name changed) and prove it is green:
python3.12 -m venv .venv && source .venv/bin/activate
make install
make gate
```

`--dist` defaults to the `--resource` value; pass it explicitly when your git id differs from
your resource stem. `--resource` is validated against the same
`^[a-z][a-z0-9-]{2,18}$` regex the Terraform `name_prefix` variable enforces, so a stem the stack
would refuse fails here instead of at plan time. `--package` must be a valid snake_case Python
identifier. Add `--include-docs` to sweep Markdown prose too; without it the script leaves
`.md` files alone so a code rename stays deterministic. The script skips itself, so the renamer
is not left half-rewritten, and it renames `src/tprm_ddq/` last, after the file contents are
rewritten. The catalog id `third-party-risk-ddq` is left alone unless you pass `--catalog-id`, so a fork stays
traceable to the entry it descends from. The script deliberately does NOT touch the human
decisions below.

## 4. The human decisions (the script can't make these)

1. **Region / residency.** The build defaults to `asia-southeast1` (MAS / Singapore), chosen once
   and shared: `config/settings.yaml:region`, `infra/terraform/render.tf.json:render_region` and
   the Terraform `region` / `allowed_regions` pair. Set all of them to your in-country region,
   and re-run the residency tests in `infra/terraform/production_edge.tftest.hcl`, which refuse a
   region outside the allowlist at plan time. See [`runbook.md`](runbook.md).
2. **Identity / IdP.** This repo owns no login flow: the `gcp` profile verifies the IAP-injected
   assertion at the edge, `local` uses seeded dev personas, and `onprem` is a client IdP
   placeholder. Wire your issuer on the deployed service (auth is configured ON the service, not
   in this code) and set `TPRM_DDQ_IAP_AUDIENCE`. An unset or emptied audience refuses every
   caller rather than verifying without one.
3. **The risk-scoring policy (your numbers).** `ScoringPolicy` in `domain/scoring_engine.py`
   holds the whole inherent-risk formula as DATA: the four factor weights (criticality 4, data 3,
   jurisdiction 2, substitutability 2), the data-classification and substitutability bands, the
   `high_risk_jurisdictions` set (the shipped `{"XX", "ZZ", "offshore-unnamed"}` is obviously a
   placeholder), the descending `inherent_thresholds` and the controls that earn residual credit.
   These are a REFERENCE, not your risk appetite. Keep the two invariants the engine encodes: a
   hard signal (a sanctions-category media hit, an adverse SOC 2 opinion, an expired certificate,
   a going-concern failure, a critical financial ratio) raises the band and can never be softened
   by narrative, and a sanctions hit forces CRITICAL outright.
4. **The control taxonomy and its evidence sources.** `domain/control_taxonomy.py` maps SOC 2
   TSC, ISO 27001 Annex A and SIG/CAIQ identifiers onto the ten-member `CanonicalControl` set,
   and `MANDATORY_CONTROLS` decides which absences become gaps. An identifier the packs do not
   know maps to nothing and is surfaced as an unmapped-evidence gap rather than guessed, which is
   the behaviour to preserve when you swap in your own frameworks.
5. **Policy numbers your risk and compliance functions own.** `FinancialPolicy` in
   `domain/financials.py` (the liquidity, leverage and going-concern band boundaries), the
   `MemoReviewPolicy` escalation floor in `domain/hitl.py` (`Severity.HIGH` today; the memo
   itself is unconditionally human either way), the jurisdiction rows and their ORDER in
   `domain/pii.py`, and the eval thresholds in `eval/run_eval.py` (`scoring_accuracy`,
   `extraction_fidelity`, `gap_recall`, `review_safety`, `pii_safety`). All of these are
   module-level or dataclass defaults today rather than a `policy:` section in
   `config/settings.yaml` (practices-audit check B4); change them deliberately and add a test
   that pins your values.
6. **Reference data is fictional.** Every fixture (`tests/fixtures/sample_cases.py`, the local
   extraction, adverse-media, contract-terms and compliance corpora under `adapters/local/`) and
   both golden datasets (`eval/datasets/golden_vendors.jsonl`,
   `eval/datasets/golden_cases.jsonl`) use obviously fake vendor names and `.example` domains.
   Replace them with your own synthetic data. **Do not run against a real vendor population
   without your own security, legal and model-risk sign-off.**
7. **Eval golden set.** Rebuild `eval/datasets/golden_vendors.jsonl` for your taxonomy and your
   scoring policy: a fork inherits a green gate that measures the WRONG numbers until you do.
   The gate structure and the strict `pii_safety >= 0.99` and `review_safety == 1.0` metrics are
   generic; the golden cases are yours.
8. **Deployment posture.** Review the Dockerfile (digest-pinned base, non-root uid 10001),
   `infra/terraform/` (Org Policy, CMEK, a dry-run-first VPC-SC perimeter, the locked WORM log
   bucket) and the loopback-by-default binding before you expose anything. The WORM lock is
   irreversible: confirm `retention_days` before the first apply. Note that
   `infra/terraform/managed_readiness.tf` deliberately REFUSES to authorise the serving edge
   while `src/tprm_ddq/managed_readiness.py` still lists construction-only managed adapters, and
   the container command runs the same preflight before Uvicorn starts. Emptying that tuple is
   part of your adoption work, not a flag to flip.

## 5. Do not duplicate the platform

This repo is one system in a catalog of composable GRC systems. Several concerns it *touches* are
owned by sibling platform services, and you should integrate rather than rebuild them (see
[`faq/features-faq.md`](faq/features-faq.md) for the full map). The `gcp` profile's adapters are
the seams those integrations switch into:

- `compliance-advisory`: the outsourcing-rule expectation and its citation behind every
  gap, over `CompliancePort` (`adapters/gcp/compliance.py`, an A2A client to `compliance-advisory`'s regulatory
  KB). This repo decides which gaps exist; it never invents regulatory text. A control with no
  requirement fetched still yields a gap, cited to the evidence, with an explicit "no rule text
  available" reference.
- `contract-obligation-extraction` contract-obligation register: the vendor's contractual commitments (audit and step-in
  rights, sub-outsourcing, residency, exit assistance, SLAs), over `ContractTermsPort`. `contract-obligation-extraction` is
  unshipped in this workspace, so the offline fixture adapter freezes the contract shape and a
  contract test pins it. Do not build a second contract register here.
- `operational-resilience-mapping` consumes the Outsourcing and Material-Arrangements Register this repo writes
  (`RegisterStorePort`, `domain/register_service.py`) over A2A. This repo owns the register rows
  and their tenant authorisation; the downstream reporting is not its job.
- `agent-registry`: this agent publishes its A2A card at
  `/.well-known/agent-card.json`; register it rather than inventing a discovery mechanism.
- `model-quality-gate` AI-quality / model-risk gate: owns promotion. `eval/run_eval.py --mode gate` is the
  client half (`TPRM_DDQ_QUALITY_URL`) and refuses to run off the managed profile; the offline
  smoke mode mirrors the thresholds but never promotes.
- `agent-observability` plus immutable WORM audit: audit events and trace spans go to it via
  `AuditSinkPort` and `ObservabilityTracerPort`. The managed tracer exports OTLP to the `agent-observability`
  collector when `OTEL_EXPORTER_OTLP_ENDPOINT` is set and to Cloud Trace when it is not.
- `human-review-console` human-review / maker-checker console: every escalation is routed to it over the shared
  `review-kit` (rule R8); you wire your endpoint (`HUMAN_REVIEW_URL`), you do not
  re-implement the console.

The guardrail gateway (`agent-guardrail-gateway`) is **not** integrated today, and neither is the enterprise knowledge
base (`enterprise-knowledge-base`). `agent-guardrail-gateway` becomes mandatory the moment untrusted free text (a vendor-written DDQ answer,
an uploaded evidence document, an adverse-media snippet) reaches a live model: see rule R1 in
[`../COMPLIANCE.md`](../COMPLIANCE.md).

## 6. Adoption checklist

- [ ] Ran `scripts/rename_fork.py`, recreated the venv, `make gate` green.
- [ ] Set the region in all three places (settings, `render.tf.json`, tfvars) and re-ran the
      Terraform residency tests.
- [ ] Wired your IdP audience on the deployed service (this repo owns no login flow).
- [ ] Replaced `ScoringPolicy` with your risk appetite, keeping the hard-signal override and the
      sanctions-forces-CRITICAL invariant.
- [ ] Swapped the framework packs and `MANDATORY_CONTROLS` in `domain/control_taxonomy.py` for
      your own taxonomy, preserving the unmapped-evidence-becomes-a-gap behaviour.
- [ ] Pointed `CompliancePort` at your regulatory KB (or loaded your outsourcing rules into
      `compliance-advisory`) and `ContractTermsPort` at your contract register.
- [ ] Owned the remaining policy numbers (financial bands, escalation floor, PII jurisdictions,
      eval thresholds) with your risk and compliance functions.
- [ ] Replaced every synthetic fixture corpus and both golden datasets.
- [ ] Rebuilt the eval golden set for your taxonomy and scoring policy.
- [ ] Reviewed the deploy posture (Dockerfile, Terraform, `retention_days`, bind address) and
      decided how you will close out `managed_readiness.py`.
- [ ] Wired your `human-review-console` review endpoint and decided which sibling services you integrate vs stub.
- [ ] Read [`model-card.md`](model-card.md) and closed its remaining controls before binding any
      live model.
- [ ] Recorded your baseline upstream tag so you can take future fixes.
