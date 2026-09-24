"""Invariant tests for the deterministic layer. No API calls, no data needed.

    python test_rubric.py
"""

from __future__ import annotations

import sys

from triage import rubric
from triage.schema import DEADLINE, ORDINALS, OUTAGE, SCOPE, WORKAROUND, WORK_TYPE

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
        "work_type": "Incident",
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
            work_type="Service Request",
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
                        for work in WORK_TYPE:
                            for service in ("NAV Calculation", "Outlook & Email"):
                                result = rubric.apply_rubric(
                                    evidence(
                                        scope=scope,
                                        outage_extent=outage,
                                        workaround=workaround,
                                        deadline_pressure=deadline,
                                        regulatory_or_security=regulatory,
                                        work_type=work,
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



def test_age_only_lifts_unresolved() -> None:
    fresh = rubric.age_factor(0.0, resolved=False)
    stale = rubric.age_factor(200.0, resolved=False)
    closed = rubric.age_factor(200.0, resolved=True)
    check("a long-open ticket ages, a closed one does not",
          stale > fresh and closed == 0.0, f"{fresh}/{stale}/{closed}")
    check("age_factor saturates at 1.0", stale == 1.0, str(stale))


def test_age_never_crosses_a_band() -> None:
    """Soft factors must reorder within a band, never jump priority."""
    ev = evidence(outage_extent="partial_degradation", workaround="none")
    young = rubric.apply_rubric(ev, "Trading Platform", age_days=0, resolved=False)
    old = rubric.apply_rubric(ev, "Trading Platform", age_days=365, resolved=False)
    check("age raises the score", old["priority_score"] > young["priority_score"],
          f"{young['priority_score']} -> {old['priority_score']}")
    check("age does not change the priority band",
          old["priority_pred"] == young["priority_pred"],
          f"{young['priority_pred']} vs {old['priority_pred']}")
    lo, hi = rubric.PRIORITY_BANDS[old["priority_pred"]]
    check("aged score stays inside its band", lo <= old["priority_score"] <= hi,
          f"{old['priority_score']} not in [{lo},{hi}]")


def test_difficulty_absent_redistributes_weight() -> None:
    """A missing difficulty signal must not silently shrink every score."""
    full = rubric.combined_offset(1.0, 1.0, 1.0)
    without = rubric.combined_offset(1.0, 1.0, None)
    check("all-max offset is 1.0 with difficulty", abs(full - 1.0) < 1e-9, str(full))
    check("all-max offset is still 1.0 without difficulty",
          abs(without - 1.0) < 1e-9, str(without))


def test_harder_peers_outrank() -> None:
    ev = evidence(outage_extent="partial_degradation", workaround="none")
    easy = rubric.apply_rubric(ev, "Trading Platform", age_days=10, resolved=False, difficulty=0.0)
    hard = rubric.apply_rubric(ev, "Trading Platform", age_days=10, resolved=False, difficulty=1.0)
    check("a historically harder peer group scores higher",
          hard["priority_score"] > easy["priority_score"],
          f"{easy['priority_score']} vs {hard['priority_score']}")


def test_work_type_round_trips() -> None:
    inc = rubric.apply_rubric(evidence(work_type="Incident"), "Trading Platform")
    req = rubric.apply_rubric(evidence(work_type="Service Request"), "Trading Platform")
    check("work_type is emitted verbatim",
          inc["work_type_pred"] == "Incident" and req["work_type_pred"] == "Service Request",
          f"{inc['work_type_pred']}/{req['work_type_pred']}")


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
