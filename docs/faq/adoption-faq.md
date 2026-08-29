# Adoption FAQ

For an engineering lead forking this repo as their institution's vendor due-diligence base. The
step-by-step is [`../ADOPTING.md`](../ADOPTING.md); this answers the "will it hurt later?"
questions.

### How do I rebrand it for my organisation?

`scripts/rename_fork.py` rewrites the package name (`tprm_ddq`, which is also the console
script), the `TPRM_DDQ_` env prefix (including the bare token that
`infra/terraform/render.tf.json` carries as `render_env_prefix`, so Terraform sets the same
variable names on the service), the Terraform `name_prefix` resource stem (`rgc8-svc`) and the
distribution / git id in one pass. Preview with `--dry-run`, apply with `--yes`, then recreate
the venv, `make install`, and run `make gate`. `--resource` is validated against the same
`^[a-z][a-z0-9-]{2,18}$` regex the Terraform variable enforces, so a bad stem fails here rather
than at plan time. The catalog id `Rgc8` is left alone unless you pass `--catalog-id`, so a fork
stays traceable to the entry it descends from. The script does the mechanical rename; the human
decisions (scoring policy, control taxonomy, region, IdP, eval golden set) are the checklist in
`ADOPTING.md`.

### If several institutions fork this, how does each take upstream fixes?

Track upstream via **git tags**. The repo declares a core-vs-adopter-owned boundary
(`ADOPTING.md` section 2): upstream owns `domain/kernel.py`, `ports/`, `tests/contract/`, the
eval harness mechanics, CI and the Terraform stack; you own `config/settings.yaml` values, the
policy dataclasses (`ScoringPolicy`, `FinancialPolicy`, `MemoReviewPolicy`), the taxonomy packs,
the fixture corpora and golden sets, `adapters/onprem/*`, UI theming and `terraform.tfvars`.
Rebase your adopter-owned changes onto each release rather than merging `main` continuously, so
conflicts stay in files you were told to expect.

### What do we have to supply that is not in this repo?

Five things, and the first four are not code here:

1. **Your risk appetite.** `ScoringPolicy` ships reference weights, bands and a placeholder
   `high_risk_jurisdictions` set of `{"XX", "ZZ", "offshore-unnamed"}`. Your risk function owns
   the real numbers.
2. **Your control taxonomy.** `domain/control_taxonomy.py` ships SOC 2 TSC, ISO 27001 Annex A and
   SIG/CAIQ packs mapped onto ten canonical controls, plus a `MANDATORY_CONTROLS` list that
   decides which absences become gaps.
3. **The regulatory KB.** `CompliancePort` fetches the outsourcing-rule expectation behind every
   gap. Point it at Rsk1 with your rules loaded, or at your own KB. Do not author rule text here.
4. **The contract register.** `ContractTermsPort` reads the vendor's commitments. Rgc12 is
   unshipped in this workspace, so the fixture adapter freezes the shape and a contract test pins
   it; wire your own register behind the unchanged port.
5. **The review console.** An Hrz7 deployment reachable at `HUMAN_REVIEW_URL`. The managed
   router REFUSES to swallow an escalation when this is empty, so a fork cannot ship rule R8
   unwired and green.

### The `gcp` adapters raise. How much work is that, really?

Ten operations, listed by name in `src/tprm_ddq/managed_readiness.py`: the three generation
methods, Document AI extraction, grounded adverse-media search, the Rsk1 compliance client, the
Rgc12 contract-terms client and the three AlloyDB register-store methods. Two things follow. The
container command and the API preflight refuse to start a `gcp` process whose bindings select any
of them, and `infra/terraform/managed_readiness.tf` refuses to authorise the serving edge. That
is deliberate: the alternative is a service that reports healthy and fails on the first real
request. Empty the tuple and flip `managed_profile_implemented` in the same reviewed commit that
lands the adapters and their integration tests.

### How do I add a new outbound dependency (a new port)?

There is a fixed touch list and a contract test that enforces it. A port must be registered in
FIVE places or it runs with no enforcement at all: `ports/__init__.py` (`PORT_PROTOCOLS`),
`config.DEFAULT_BINDINGS`, a `Container` accessor, `config/settings.yaml`, and a `PortCase` in
`tests/contract/canonical.py`. Then bind it in all three families.
`tests/contract/test_port_parity.py` asserts set equality across the five. See
[`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

### Can I retune the scoring policy without touching engine code?

Partly today, and this is stated honestly. The policy is already **data**: `ScoringPolicy`,
`FinancialPolicy` and `MemoReviewPolicy` are frozen dataclasses the engines take as parameters,
and the framework packs are frozen module tables, so retuning is not an algorithm edit. But there
is **not yet** a `policy:` block in `config/settings.yaml` that a deployment could carry its own
numbers in without a code change, and the PII jurisdiction list and the eval thresholds are
module constants. That is the open B4 item in [`../practices-audit.md`](../practices-audit.md).
If your risk function must own these as configuration, plan that small addition as part of
adoption. Note the contrast with a sibling repo that already loads its thresholds from an
adopter-owned YAML pack: the pattern is proven, it is just not applied here yet.

### Does the gate run for my fork out of the box?

Yes. `make gate` is offline, credential-free and network-free (ruff, ruff format, mypy strict,
the whole suite except integration, and the eval), and the CI workflow references no `secrets.`,
so a fork's build is green immediately. You add secrets only when you wire the `gcp` profile.
Note the eval measures the REFERENCE scoring policy and golden vendors until you rebuild them for
your own taxonomy; that is an explicit adoption step, not a silent pass.

### Will the demo rot after I diverge?

It is guarded, and the guard is inside the gate. A demo step lives in `demo.STEPS` and in
`walkthrough.CHECKS`, and `tests/unit/test_demo_surface.py` holds the two equal, so a claim the
demo makes but nobody verifies cannot exist. The same test also asserts that every `*.py` in
`scripts/` is described in `scripts/README.md`, so the demo surface cannot silently grow an
undocumented tool. `make demo-selftest` runs the whole arc headless over the real loopback server
and exits non-zero when a claim stops being true; the demo-gate workflow runs it,
`make portability`, `make demo-static` and `make docs-check` on every push. If you diverge, keep
the step keys and the `facts` dict the checks read.

### The eval reports 1.000. Should we believe it?

Only because each metric is proved able to report something else.
`tests/unit/test_not_falsely_green.py` and `tests/unit/test_eval_metrics_go_red.py` hand each
metric a planted mutant and fail the build if it still passes. A metric that cannot go red is not
a metric. The scores are also measured against the REFERENCE golden vendors, which are synthetic:
rebuilding them for your taxonomy is adoption step 7.

### What is still open?

[`../practices-audit.md`](../practices-audit.md) carries the per-check verdict and the work list.
The three that matter most before production: implementing the ten managed operations, exposing
the full assessment pipeline on a serving surface (today only the triage path has HTTP, CLI and
agent routes), and registering this repo's metric bundle with Hrz4 so `eval/run_eval.py --mode
gate` has an authority to ask. The Terraform stack is written, validated and tested against a
mocked provider; it has never been applied.
