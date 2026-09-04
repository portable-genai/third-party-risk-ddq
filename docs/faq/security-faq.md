# Security FAQ

For AppSec and security architecture. Every answer names the file that is the evidence, so the
review can read the control rather than the claim.

### Who is the actor on a decision, and can a caller assert it?

A server-verified `Principal`, always. The request schema has no `actor` field: the audit actor
and the review maker both come from the identity adapter, and every client-supplied actor,
tenant, role, ACL and authorization header is discarded at the browser boundary
(`ui/lib/embed-policy.mjs`). Under the `gcp` profile the adapter verifies the IAP-injected
assertion against the configured audience, against IAP's own key set and against the issuer
(`adapters/gcp/identity.py`); an unset or emptied `TPRM_DDQ_IAP_AUDIENCE` REFUSES every caller,
because `audience=None` means google-auth does not verify the audience at all and would accept
any Google-signed token from any project.

### How is tenant isolation enforced?

Server-side, in the domain rather than in a store adapter. `domain/register_service.py`
authorises a register read against the VERIFIED principal's tenant and denies a cross-tenant
attempt with 403 (`CrossTenantError`), never a silent 404. `RegisterStorePort.get` is documented
to return `None` for a row that exists under a different tenant, so the tenant is part of the
row's identity rather than a filter a caller could omit. Keeping the check in the domain means
every driving surface inherits it and no single adapter becomes the only place the boundary
exists. `COMPLIANCE.md` still marks tenant isolation Partial: object-level authorisation from
data tags is the piece that is owed once this service gains a broader queryable store.

### What happens if the profile variable goes missing in production?

The process still binds the SDK-free adapters (the alternative is importing cloud SDKs that are
not installed), but nobody chose them, so every relaxation is withdrawn: the seeded dev personas
refuse to construct, no service-to-service scheme is selected, the dev CORS allowlist and the
`X-Dev-Persona` header are gone, the interactive docs are not registered, and the loopback
exposure guard refuses every route to any non-loopback peer. An emptied or mis-capitalised value
raises AT IMPORT, so the process fails to boot rather than serving on a posture nobody chose
(`config.py`, `tests/unit/test_profile_single_source.py`).

### Does setting the service-to-service token open anything?

No, and this is enforced rather than intended. The exposure guard's posture is derived from the
identity BINDING (the adapter declares `VERIFIED` / `CLIENT_ASSERTED` / `UNIMPLEMENTED`), never
from a credential. `TPRM_DDQ_S2S_TOKEN` authenticates a calling SERVICE and no end user.
`tests/unit/test_end_user_auth_posture.py` walks the guard's argument through the constants it
names and fails the build if a credential reappears at any depth, because it did once: setting
the token switched the guard off for the end-user routes it was protecting.

### Can a half-built managed profile be served by accident?

No, and this is unusual enough to call out. Ten managed operations in this repo are
construction-only placeholders that raise. `src/tprm_ddq/managed_readiness.py` lists them by
name; `assert_managed_profile_ready` refuses to let a `gcp` or `platform` process start when the
bound adapter map selects one of them, and it is called both from the API preflight
(`api/app.py`) and from the container command in the Dockerfile, so it runs before Uvicorn does.
The same fact is mirrored in Terraform: `infra/terraform/managed_readiness.tf` fails the
`managed_profile_is_implemented_before_serving` check whenever `production_edge_enabled` is true,
so the plan describes the hardened edge and refuses to authorise it.

### Where does personal data go?

It is masked before it crosses any boundary, not once at the end. Redaction runs before the audit
write (`domain/triage_service.py`, `domain/assessment_service.py`), before a review payload
leaves the process (`adapters/_review_payload.py`, against EVERY jurisdiction's rows because the
console is a shared sink), and before a tool result can enter a model's context
(`agent/tools.py`). The pattern set and its ORDER are this vertical's (`domain/pii.py`, national
rows first, universal rows last), drawn from the shared `pii-kit`. The `pii_safety` eval metric
holds this at `>= 0.99`, scored two ways, and `tests/unit/test_not_falsely_green.py` proves the
metric can go red.

### Can a model exfiltrate or invent anything?

Not today, because no model runs: the only `GenerationPort` adapter that answers is a
deterministic rule-based stub and the managed one raises. Before you bind a real one, read
[`../model-card.md`](../model-card.md): the output-validation control does NOT exist yet. A
draft's `grounded_gap_ids` are used without checking them against the gap set the engine
produced, and the memo prose is stored without a figure allowlist. Prompt-injection screening
through the `agent-guardrail-gateway` is also not wired, and this vertical's inputs are written by
the party being assessed, so both controls belong in the same change (rule R1 in
`COMPLIANCE.md`).

### How is the audit trail protected?

Append-only and hash-chained, AND externally anchored. The chain catches an edit, a deletion or a
reorder; only the anchor catches a TRUNCATED TAIL, because dropping the newest rows leaves a
shorter chain that verifies perfectly. `audit_anchor_path` (`TPRM_DDQ_AUDIT_ANCHOR`) writes the
chain head to a file on another volume, and `tests/unit/test_audit_anchor.py` proves the
detection, proves the control case goes UNDETECTED without an anchor, and proves an append after
truncation refuses rather than re-anchoring. Under the managed profile the sink is a locked Cloud
Logging bucket (`infra/terraform/logging_worm.tf`), which provides non-rewritability itself.

### What about supply chain?

Both lockfiles are committed and pin every dependency exactly; the catalog commons are pinned to
40-character COMMIT shas rather than tags, because a re-pushed tag changes what installs with no
diff in the lockfile. The base image is digest-pinned, Actions are SHA-pinned, dependabot covers
pip, docker, github-actions and npm, and `pip-audit` plus `npm audit --audit-level=high` are HARD
CI failures. `tests/unit/test_repo_artifacts.py` asserts each of these from inside the repo, and
it asks git whether each pinned sha is a COMMIT object rather than an annotated tag object, which
a regular expression cannot tell apart.

### What is deliberately out of scope?

- **Login.** This repo authenticates nobody itself: the platform in front of it does, and the UI
  forwards the assertion without parsing or trusting a parsed copy.
- **Injection defence and output filtering.** Owned by `agent-guardrail-gateway`; not bound yet.
- **The review queue.** Owned by `human-review-console`; this repo produces escalations and routes them.
- **Regulatory text.** Owned by `compliance-advisory`; this repo cites it and never authors it.
- **Network egress control.** VPC-SC governs access to Google APIs across perimeters, not
  arbitrary internet egress. The private-egress rule that lets this service reach the `compliance-advisory` KB,
  the `contract-obligation-extraction` register and the `human-review-console` and nothing else is an adopter network decision, called
  out in `COMPLIANCE.md` P-01.
