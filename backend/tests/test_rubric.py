"""Rubric invariants, ported from feature/apertus-triage (data/test_rubric.py)."""

import itertools
from typing import get_args

import pytest

from app.domain import LEVELS, priority_for
from app.pipeline.rubric import PRIORITY_BANDS, apply_rubric, priority_score, rescore
from app.schemas import Deadline, Facts, Outage, Scope, Workaround

CRITICAL, NON_CRITICAL = "NAV Calculation", "Outlook & Email"


def facts(**kw) -> Facts:
    base = dict(scope="one_entity", outage_extent="partial_degradation", workaround="none",
                regulatory_or_security=False, deadline_pressure="none")
    return Facts(**(base | kw))


ALL_FACTS = [
    Facts(scope=s, outage_extent=o, workaround=w, regulatory_or_security=r, deadline_pressure=d)
    for s, o, w, r, d in itertools.product(get_args(Scope), get_args(Outage), get_args(Workaround), (True, False), get_args(Deadline))
]


def test_every_combination_gives_a_consistent_verdict():
    # 5 scopes x 3 outages x 4 workarounds x 2 x 3 deadlines = 360 facts x 2 services x 2 work types
    assert len(ALL_FACTS) == 360
    for f, service, work_type in itertools.product(ALL_FACTS, (CRITICAL, NON_CRITICAL), ("Incident", "Service Request")):
        r = apply_rubric(f, service, work_type)
        assert r.priority == priority_for(r.urgency, r.impact)
        low, high = PRIORITY_BANDS[r.priority]
        assert low < r.priority_score < high
        assert len(r.trace) == 3


def test_score_is_monotone_with_priority():
    ranks = {p: i for i, p in enumerate(reversed(LEVELS))}  # Lowest=0 .. Highest=4
    top_of_lower = [priority_score(p, 1.0) for p in sorted(PRIORITY_BANDS, key=ranks.get)]
    bottom_of_higher = [priority_score(p, 0.0) for p in sorted(PRIORITY_BANDS, key=ranks.get)]
    for i in range(len(top_of_lower) - 1):
        assert top_of_lower[i] < bottom_of_higher[i + 1]


def test_critical_full_outage_is_highest():
    r = apply_rubric(facts(outage_extent="full_unavailability"), CRITICAL, "Incident")
    assert (r.impact, r.urgency, r.priority) == ("Highest", "Highest", "Highest")


def test_routine_request_stays_low():
    r = apply_rubric(facts(outage_extent="none", workaround="not_applicable", scope="individual"), NON_CRITICAL, "Service Request")
    assert r.priority == "Lowest"


def test_criticality_raises_impact():
    assert apply_rubric(facts(), CRITICAL, "Incident").impact == "High"
    assert apply_rubric(facts(), NON_CRITICAL, "Incident").impact == "Medium"


def test_regulatory_breach_escalates():
    assert apply_rubric(facts(regulatory_or_security=True), NON_CRITICAL, "Incident").urgency == "Highest"


def test_age_lifts_open_tickets_but_never_crosses_a_band():
    fresh = apply_rubric(facts(), CRITICAL, "Incident", age_days=0)
    old = apply_rubric(facts(), CRITICAL, "Incident", age_days=500)
    assert fresh.priority == old.priority
    assert fresh.priority_score < old.priority_score < PRIORITY_BANDS[old.priority][1]


def test_resolved_tickets_do_not_age():
    a = apply_rubric(facts(), CRITICAL, "Incident", age_days=90, resolved=True)
    assert a.priority_score == apply_rubric(facts(), CRITICAL, "Incident", age_days=0).priority_score


def test_rescore_keeps_position_in_new_band():
    score = priority_score("High", 0.5)
    moved = rescore("High", score, "Low")
    assert moved == priority_score("Low", 0.5)
    assert rescore("High", score, "High") == score
