"""Every eval metric must be provably able to go RED, per segment (a metric that cannot is none).

Each metric scores the REAL engine against the dataset's own expected label. The green case is a
correctly-labelled vendor; the red case is the SAME shape with a label the engine cannot satisfy,
so a metric that stays green on the red case is falsely green and proves nothing.
"""

from __future__ import annotations

import copy
from typing import Any

from agent_eval_kit import assert_each_can_go_red
from eval.run_eval import extraction_score, gap_score, scoring_score

_HARBOR: dict[str, Any] = {
    "id": "green-harbor",
    "vendor": "Harbor Managed Print (FICTIONAL)",
    "criticality": "low",
    "data_classification": "internal",
    "jurisdiction": "SG",
    "substitutability": "commodity",
    "documents": ["CONTROL soc2 CC6.1 effective 2025-07-01", "DDQ sig_caiq IAM MFA enforced"],
    "media_subject": "Harbor Managed Print (FICTIONAL)",
    "expected_inherent": "low",
    "expected_residual": "low",
    "expected_controls": ["access_control"],
    "expected_gap_controls": [],
}

_CORNERSTONE: dict[str, Any] = {
    "id": "green-cornerstone",
    "vendor": "Cornerstone Payments Inc (FICTIONAL)",
    "criticality": "high",
    "data_classification": "confidential",
    "jurisdiction": "XX",
    "substitutability": "moderate",
    "documents": [
        "CONTROL soc2 CC6.1 partial 2025-06-01",
        "CONTROL soc2 CC6.6 ineffective 2025-06-01",
        "CONTROL soc2 C1.1 ineffective 2025-06-01",
        "CONTROL iso27001 A.5.29 untested 2022-01-01 expired",
        "DDQ sig_caiq SEF incident response is planned",
        "DDQ sig_caiq LOG no central logging yet",
    ],
    "media_subject": "Cornerstone Payments Inc (FICTIONAL)",
    "expected_inherent": "medium",
    "expected_residual": "high",
    "expected_controls": ["access_control", "encryption", "data_governance", "business_continuity"],
    "expected_gap_controls": ["incident_response", "logging_monitoring", "encryption"],
}


def _with(case: dict[str, Any], **changes: Any) -> dict[str, Any]:
    out = copy.deepcopy(case)
    out.update(changes)
    return out


def test_scoring_accuracy_can_go_red() -> None:
    # green: expected residual matches the engine; red: an impossible expected band for a low case.
    assert_each_can_go_red(
        scoring_score,
        {"low-vendor": (_HARBOR, _with(_HARBOR, expected_residual="critical"))},
        threshold=0.80,
        metric="scoring_accuracy",
    )


def test_extraction_fidelity_can_go_red() -> None:
    # red: expect a control the single document cannot yield, so recall drops below the bar.
    red = _with(_HARBOR, expected_controls=["access_control", "encryption"])
    assert_each_can_go_red(
        extraction_score,
        {"low-vendor": (_HARBOR, red)},
        threshold=0.90,
        metric="extraction_fidelity",
    )


def test_gap_recall_can_go_red() -> None:
    # red: a well-controlled vendor with no gaps, but a label expecting one, so recall is 0.
    red = _with(_HARBOR, expected_gap_controls=["access_control"])
    assert_each_can_go_red(
        gap_score,
        {"weak-vendor": (_CORNERSTONE, red)},
        threshold=0.80,
        metric="gap_recall",
    )
