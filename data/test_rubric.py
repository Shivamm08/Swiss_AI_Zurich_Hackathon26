"""Invariant tests for the deterministic layer. No API calls, no data needed.

    python test_rubric.py
"""

from __future__ import annotations

import sys

from triage import rubric
from triage.schema import DEADLINE, ORDINALS, OUTAGE, SCOPE, WORKAROUND

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {name}")
    else:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL  {name}  {detail}")


def evidence(**overrides) -> dict:
    base = {
        "scope": "one_entity",
        "outage_extent": "partial_degradation",
        "workaround": "easy",
        "regulatory_or_security": False,
        "deadline_pressure": "none",
        "is_request": False,
    }
    base.update(overrides)
    return base


def test_matrix_matches_readme() -> None:
    """The matrix is graded, so it is transcribed and checked cell by cell."""
    expected = {
        ("highest", "highest"): "highest", ("highest", "high"): "highest",
        ("highest", "medium"): "high", ("highest", "low"): "medium",
        ("highest", "lowest"): "medium",
        ("high", "highest"): "highest", ("high", "high"): "high",
        ("high", "medium"): "high", ("high", "low"): "medium",
        ("high", "lowest"): "low",
        ("medium", "highest"): "high", ("medium", "high"): "high",
        ("medium", "medium"): "medium", ("medium", "low"): "low",
        ("medium", "lowest"): "low",
        ("low", "highest"): "medium", ("low", "high"): "medium",
        ("low", "medium"): "low", ("low", "low"): "low",
        ("low", "lowest"): "lowest",
        ("lowest", "highest"): "medium", ("lowest", "high"): "low",
        ("lowest", "medium"): "low", ("lowest", "low"): "lowest",
        ("lowest", "lowest"): "lowest",
    }
    bad = [
        f"U={u} I={i} got {rubric.PRIORITY_MATRIX[u][i]} want {want}"
        for (u, i), want in expected.items()
        if rubric.PRIORITY_MATRIX[u][i] != want
    ]
    check("priority matrix matches the README, all 25 cells", not bad, "; ".join(bad[:3]))


def test_score_is_monotone_with_priority() -> None:
    """Sorting by priority_score must never contradict the categorical label."""
    ranks = {level: i for i, level in enumerate(ORDINALS)}
    seen: list[tuple[int, float]] = []
    for priority in ORDINALS:
        for offset in (0.0, 0.5, 1.0):
            seen.append((ranks[priority], rubric.priority_score(priority, offset)))
    violations = [
        (a, b)
        for a in seen
        for b in seen
        if a[0] < b[0] and a[1] >= b[1]
    ]
    check("priority_score never crosses a band boundary", not violations, str(violations[:2]))


def test_score_bounds() -> None:
    values = [
        rubric.priority_score(p, o)
        for p in ORDINALS
        for o in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    check("priority_score stays within 0..1", all(0.0 <= v <= 1.0 for v in values))


def test_critical_outage_escalates() -> None:
    result = rubric.apply_rubric(
        evidence(outage_extent="full_unavailability", workaround="none"),
        "NAV Calculation",
    )
    check(
        "critical service, full outage -> highest/highest/highest",
        (result["impact_pred"], result["urgency_pred"], result["priority_pred"])
        == ("highest", "highest", "highest"),
        str(result),
    )


def test_routine_request_stays_low() -> None:
    result = rubric.apply_rubric(
        evidence(
            scope="individual",
            outage_extent="none",
            workaround="not_applicable",
            is_request=True,
        ),
        "Identity & Access Management",
    )
    check(
        "routine access request -> lowest impact and urgency",
        result["impact_pred"] == "lowest" and result["urgency_pred"] == "lowest",
        str(result),
    )
    check("routine access request -> low priority score", result["priority_score"] < 0.2)


def test_criticality_raises_severity() -> None:
    args = dict(outage_extent="partial_degradation", workaround="none")
    critical = rubric.apply_rubric(evidence(**args), "Trading Platform")
    ordinary = rubric.apply_rubric(evidence(**args), "SharePoint & File Storage")
    check(
        "same symptoms score higher on a critical service",
        critical["priority_score"] > ordinary["priority_score"],
        f"{critical['priority_score']} vs {ordinary['priority_score']}",
    )


def test_regulatory_breach_escalates() -> None:
    plain = rubric.apply_rubric(evidence(workaround="none"), "Tax Reporting")
    breach = rubric.apply_rubric(
        evidence(workaround="none", regulatory_or_security=True), "Tax Reporting"
    )
    check(
        "a regulatory breach raises urgency",
        ORDINALS.index(breach["urgency_pred"]) > ORDINALS.index(plain["urgency_pred"]),
        f"{breach['urgency_pred']} vs {plain['urgency_pred']}",
    )


def test_total_coverage() -> None:
    """Every reachable evidence combination must produce a valid verdict."""
    bad = []
    for scope in SCOPE:
        for outage in OUTAGE:
            for workaround in WORKAROUND:
                for deadline in DEADLINE:
                    for regulatory in (True, False):
                        for is_request in (True, False):
                            for service in ("NAV Calculation", "Outlook & Email"):
                                result = rubric.apply_rubric(
                                    evidence(
                                        scope=scope,
                                        outage_extent=outage,
                                        workaround=workaround,
                                        deadline_pressure=deadline,
                                        regulatory_or_security=regulatory,
                                        is_request=is_request,
                                    ),
                                    service,
                                )
                                if (
                                    result["impact_pred"] not in ORDINALS
                                    or result["urgency_pred"] not in ORDINALS
                                    or not 0.0 <= result["priority_score"] <= 1.0
                                ):
                                    bad.append(result)
    check(f"all {len(SCOPE)*len(OUTAGE)*len(WORKAROUND)*len(DEADLINE)*2*2*2} combinations are valid", not bad, str(bad[:1]))


if __name__ == "__main__":
    print("Deterministic rubric invariants\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED")
        sys.exit(1)
    print("All invariants hold.")
