from datetime import datetime, timezone

from app.pipeline import confidence
from app.pipeline.classify import Extraction, _vote


def test_overall_is_the_weakest_part_times_flags():
    c = confidence.score(votes=0.95, retrieval=0.7, flags=[], heuristic=False)
    assert c.overall == 0.7
    flagged = confidence.score(votes=0.95, retrieval=0.7, flags=["generic_service"], heuristic=False)
    assert flagged.overall == round(0.7 * 0.6, 3)


def test_heuristic_is_always_low_confidence():
    c = confidence.score(votes=1.0, retrieval=1.0, flags=[], heuristic=True)
    assert c.overall == confidence.HEURISTIC_OVERALL and "heuristic_fallback" in c.flags


def test_retrieval_score_rescales_and_caps():
    assert confidence.retrieval_score(0.70, matched=True) == 1.0
    assert confidence.retrieval_score(0.50, matched=True) == 0.5
    assert confidence.retrieval_score(0.90, matched=False) == confidence.NO_MATCH_CAP
    assert confidence.retrieval_score(None, matched=True) == confidence.KEYWORD_MATCH_SCORE


def test_routes():
    assert confidence.route_for(0.85) == "auto"
    assert confidence.route_for(0.6) == "review"
    assert confidence.route_for(0.3) == "triage"


def test_sla_due():
    t0 = datetime(2026, 9, 25, 9, tzinfo=timezone.utc)
    assert (confidence.sla_due(t0, "Highest") - t0).total_seconds() == 3600


def _ex(**kw) -> Extraction:
    base = dict(work_type="Incident", service="NAV Calculation", scope="one_entity", outage_extent="partial_degradation",
                workaround="none", regulatory_or_security=False, deadline_pressure="none", resolution="done",
                playbook_ref=None, rationale="r")
    return Extraction(**(base | kw))


def test_vote_takes_majority_and_measures_agreement():
    merged, agreement, score = _vote([_ex(), _ex(), _ex(scope="team", service="Fund Pricing")])
    assert merged.scope == "one_entity" and merged.service == "NAV Calculation"
    assert agreement["scope"] == round(2 / 3, 3) and agreement["work_type"] == 1.0
    assert 0.8 < score < 1.0
