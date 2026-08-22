"""The evidence ledger: control observations keyed by canonical control.

A pure, immutable-by-convention collection the scoring and gap engines read. It carries every
:class:`~.tprm_models.EvidenceItem` gathered from DDQ answers, SOC 2 / ISO reports, financial
statements and adverse media, indexed by the canonical control each maps to. The ledger owns no
policy: it answers "what is evidenced for this control, and how strongly", and the engines turn
that into numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .control_taxonomy import MANDATORY_CONTROLS
from .tprm_models import (
    EFFECTIVENESS_RANK,
    CanonicalControl,
    ControlEffectiveness,
    EvidenceItem,
)


@dataclass(frozen=True, slots=True)
class EvidenceLedger:
    """Evidence items grouped by canonical control. Build once from parsed sources, then read."""

    items: tuple[EvidenceItem, ...] = field(default_factory=tuple)

    def for_control(self, control: CanonicalControl) -> tuple[EvidenceItem, ...]:
        """Every item evidencing ``control``, in insertion order (deterministic)."""
        return tuple(item for item in self.items if item.control == control)

    def controls_present(self) -> frozenset[CanonicalControl]:
        """The set of controls with at least one evidence item."""
        return frozenset(item.control for item in self.items)

    def missing_mandatory(self) -> tuple[CanonicalControl, ...]:
        """Mandatory controls with no evidence item at all, in policy order (deterministic)."""
        present = self.controls_present()
        return tuple(c for c in MANDATORY_CONTROLS if c not in present)

    def best_effectiveness(self, control: CanonicalControl) -> ControlEffectiveness:
        """The strongest evidenced effectiveness for ``control``, or ABSENT if unevidenced.

        The strongest reading is used for the residual credit: a control the firm can show
        operating effectively somewhere is not un-mitigated. Weaknesses are surfaced separately
        as gaps, so a single effective attestation does not bury a failing test.
        """
        items = self.for_control(control)
        if not items:
            return ControlEffectiveness.ABSENT
        return max(items, key=lambda i: EFFECTIVENESS_RANK[i.effectiveness]).effectiveness

    def stale_items(self, as_of: date, *, max_age_days: int) -> tuple[EvidenceItem, ...]:
        """Items older than ``max_age_days`` relative to ``as_of`` (no clock beyond ``as_of``)."""
        return tuple(item for item in self.items if (as_of - item.as_of).days > max_age_days)

    def adverse_opinions(self) -> tuple[EvidenceItem, ...]:
        """Items flagged with a qualified/adverse opinion (a hard signal for scoring)."""
        return tuple(item for item in self.items if item.adverse_opinion)

    def expired_items(self) -> tuple[EvidenceItem, ...]:
        """Items flagged expired, e.g. a lapsed ISO certificate (a hard signal for scoring)."""
        return tuple(item for item in self.items if item.expired)
