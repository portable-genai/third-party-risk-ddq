# How the third-party risk service is evaluated

Read this page if you decide what this service is allowed to score. The metrics, the bars and the
corpus below are generated from the artifacts that actually gate the build, so they cannot drift
from what runs: `make evals-doc-check` fails the build when this page and those artifacts
disagree.

## How to run it

```sh
make eval              # offline, no credentials
make evals-doc-check   # this page is still true
```

`make gate` runs both on every change.

## The leak scan covers the register, not only the audit trail

`pii_safety` read the audit records and nothing else. C3 in this repository's own practices audit
records the vendor REGISTER as the sink a citation actually leaked into:
`AssessmentService.assess` hands the same citation tuple to the audit writer and to
`RegisterEntry`, and for a while only the first masked it, so an extraction citation's snippet
reached a long-lived tenant-scoped store that another service reads over A2A.

That leak is closed, in construction. What was missing was the MEASUREMENT: with the register
outside the scan window, removing the mask would have broken a unit test and left `pii_safety` at
a green 1.000, because the metric could not see the sink. A fix nothing scores is a fix that lasts
until somebody refactors it.

`vendor` and `tenant` stay outside the window on purpose. They are the row identity the store
authorises on, so a scan that read them would go permanently red on any vendor whose NAME matched
a pattern row, and a metric nobody can make green gets deleted rather than fixed.

## What is measured, and against what bar

Every bar below lives in `eval/rubrics/*.yaml` next to the argument for it, and the
runner reads it from there. There is no dict of thresholds in the runner any more: a
metric scored with no reviewed bar fails the build, and so does a bar that names no
metric, which is the direction that rots quietly because it rots toward looking well
governed.

The third column is the denominator rule, and it applies only where a score is a
FRACTION over scored positives: such a threshold `t` tolerates a single miss only over
at least `1/(1-t)` of them. `all or nothing` marks a bar that already asks for no
headroom, so a bigger corpus would not change what it means. Each rubric declares which
it is rather than the rule being guessed from the number.

| Metric | Bar | Denominator | What it measures |
|---|---|---|---|
| `extraction_fidelity` | 0.9 | a rate; needs 10 positives | Every control claim a reviewer read out of the vendor's evidence is extracted from it. |
| `gap_recall` | 0.8 | a rate; needs 5 positives | Every control gap a reviewer recorded for the vendor is surfaced by the engine. |
| `pii_safety` | 1 | all or nothing | No raw identifier survives into an audit record or into the long-lived vendor register, checked by the shared pack and by an independent planted literal. |
| `review_safety` | 1 | all or nothing | Every assessment requires human review and routes to the review console. |
| `scoring_accuracy` | 1 | all or nothing | The residual risk band the engine computes equals the band a reviewer derived by hand. |

Scored over 4 golden vendors.

## What is exercised

- **4 golden vendors** in `eval/datasets/golden_vendors.jsonl`, carrying
  27 evidence documents, 13 expected control claims and 5 expected
  control gaps between them. Those last two are the denominators
  `extraction_fidelity` and `gap_recall` are actually measured over; the vendor count is
  the number a case-count check would have used, and it supports neither bar.
- **1 of them plant a raw identifier**, so the leak metric has a target it could
  miss.

## How a metric is prevented from being decoration

1. **The bars are read from the rubrics, in both directions.** This repository had no rubric
   directory at all: every bar was an unlabelled module constant, which is exactly what practice
   E1 asks a repository not to do.
2. **One bar said less than it meant.** `scoring_accuracy` at 0.80 over four vendors was
   arithmetically identical to 1.0, since a 0.80 bar tolerates one miss only over five and three
   of four is 0.75. It now says 1.0, which is also what the property means: the residual band is
   computed deterministically from the profile and the evidence, and there is no sampling in it
   for a rate to describe.
3. **The denominator rule is asserted against what actually divides each rate**, and the vendor
   count is the wrong number for both of the remaining rates: extraction fidelity over the control
   claims a reviewer read out of the evidence, gap recall over the gaps they recorded.
4. **The golden set must plant an identifier.** A leak metric over a corpus with nothing to leak
   is a vacuous 1.0, and the runner refuses one.

## What is NOT measured here

- **A real model's words.** Every metric scores a deterministic core against a deterministic fake
  model adapter.
- **Precision of the gaps.** `gap_recall` is deliberately one-directional: an extra gap on a
  vendor already going to review costs an analyst a paragraph, while a missed gap is a control
  nobody asked the vendor about before the contract was signed.
- **Production traffic.** Everything here is a golden set. Nothing samples live requests.
