"""Deterministic contract-versus-evidence diff (slice 3).

The contract-terms port returns the vendor's contractual commitments from Rgc12 (audit and
step-in rights, sub-outsourcing, data residency, exit assistance, SLAs), each keyed to the
canonical control it evidences. This engine diffs those commitments against the evidence ledger
deterministically: a commitment the contract makes but the evidence contradicts is a mismatch,
each citing BOTH the clause and the contradicting evidence item. The model does nothing here.
"""

from __future__ import annotations

from .evidence_ledger import EvidenceLedger
from .tprm_models import (
    EFFECTIVENESS_RANK,
    ContractCommitment,
    ContractMismatch,
    ControlEffectiveness,
)

#: A commitment the contract asserts is contradicted when the evidenced effectiveness is at or
#: below this rank (ABSENT or INEFFECTIVE). PARTIAL and above is a weakness, surfaced as a gap
#: elsewhere, not a contract contradiction.
_CONTRADICTION_CEILING = EFFECTIVENESS_RANK[ControlEffectiveness.INEFFECTIVE]


def diff_contract(
    commitments: tuple[ContractCommitment, ...], ledger: EvidenceLedger
) -> tuple[ContractMismatch, ...]:
    """Return the deterministic mismatches between contract commitments and evidence.

    Two mismatch shapes, both citing clause and evidence:

    * the contract makes a commitment (``present``) but the evidence contradicts it (the control
      is absent or tested ineffective), and
    * the contract lacks a commitment (``present`` is False) for a control the evidence shows the
      vendor relies on, so there is no contractual hook for it.
    """
    mismatches: list[ContractMismatch] = []
    for commitment in commitments:
        items = ledger.for_control(commitment.control)
        if commitment.present:
            contradicting = [
                item
                for item in items
                if EFFECTIVENESS_RANK[item.effectiveness] <= _CONTRADICTION_CEILING
            ]
            if contradicting:
                worst = min(contradicting, key=lambda i: EFFECTIVENESS_RANK[i.effectiveness])
                mismatches.append(
                    ContractMismatch(
                        control=commitment.control,
                        description=(
                            f"contract commits to {commitment.term!r} but evidence tests the "
                            f"control {worst.effectiveness.value}"
                        ),
                        clause_citation=commitment.citation,
                        evidence_citation=worst.citation,
                    )
                )
        elif items:
            strongest = max(items, key=lambda i: EFFECTIVENESS_RANK[i.effectiveness])
            mismatches.append(
                ContractMismatch(
                    control=commitment.control,
                    description=(
                        f"no contractual commitment for {commitment.term!r} despite evidence the "
                        "vendor operates the control"
                    ),
                    clause_citation=commitment.citation,
                    evidence_citation=strongest.citation,
                )
            )
    return tuple(mismatches)
