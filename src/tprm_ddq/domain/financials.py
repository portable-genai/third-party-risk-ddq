"""Deterministic financial-health engine (the Doc2 covenant split).

The model EXTRACTS figures from a vendor's financial statement into
:class:`~.tprm_models.FinancialFigures`; this engine computes liquidity, leverage and
going-concern status from them. Prose can never override a computed status: the numbers here
are the record, and the narrative merely describes them.

Pure stdlib, explicit thresholds carried on a frozen policy dataclass so every band boundary is
adopter-owned rather than a buried constant.
"""

from __future__ import annotations

from dataclasses import dataclass

from .kernel import Severity
from .tprm_models import FinancialFigures, FinancialStatus


@dataclass(frozen=True, slots=True)
class FinancialPolicy:
    """Band boundaries for the financial ratios. Every number is the adopter's to set."""

    #: current ratio below this is CRITICAL liquidity; below the weak line is HIGH.
    current_ratio_critical: float = 1.0
    current_ratio_weak: float = 1.5
    #: debt-to-equity above this is CRITICAL leverage; above the elevated line is HIGH.
    debt_to_equity_critical: float = 3.0
    debt_to_equity_elevated: float = 2.0


def _safe_ratio(numerator: float, denominator: float) -> float:
    """Ratio with a zero/negative denominator treated as the worst case, not a crash.

    A vendor with zero or negative equity/liabilities is not healthier for dividing by a small
    number; it is the degenerate case, so the ratio saturates to a large sentinel that lands in
    the worst band deterministically.
    """
    if denominator <= 0:
        return float("inf")
    return round(numerator / denominator, 4)


def assess_financials(
    figures: FinancialFigures, *, policy: FinancialPolicy | None = None
) -> FinancialStatus:
    """Compute the deterministic financial status from extracted figures."""
    pol = policy or FinancialPolicy()
    current_ratio = _safe_ratio(figures.current_assets, figures.current_liabilities)
    debt_to_equity = _safe_ratio(figures.total_debt, figures.total_equity)

    if current_ratio < pol.current_ratio_critical:
        liquidity = Severity.CRITICAL
    elif current_ratio < pol.current_ratio_weak:
        liquidity = Severity.HIGH
    else:
        liquidity = Severity.LOW

    if debt_to_equity > pol.debt_to_equity_critical:
        leverage = Severity.CRITICAL
    elif debt_to_equity > pol.debt_to_equity_elevated:
        leverage = Severity.HIGH
    else:
        leverage = Severity.LOW

    return FinancialStatus(
        current_ratio=current_ratio if current_ratio != float("inf") else -1.0,
        debt_to_equity=debt_to_equity if debt_to_equity != float("inf") else -1.0,
        liquidity=liquidity,
        leverage=leverage,
        going_concern=not figures.going_concern_flag,
        citation=figures.citation,
    )
