from types import SimpleNamespace as NS

from app.pipeline import draft
from app.pipeline.retrieve import RELEVANCE_MIN, relevant


def ranked(*refs):
    return [(r, 1.0 / (i + 1)) for i, r in enumerate(refs)]


def test_clear_match_keeps_only_close_documents():
    sims = {"card": 0.79, "pb1": 0.37, "pb2": 0.34}  # "what does Rimes cover?"
    assert [r for r, _ in relevant(ranked("card", "pb1", "pb2"), sims)] == ["card"]


def test_broad_match_keeps_several():
    sims = {"a": 0.61, "b": 0.60, "c": 0.57, "d": 0.53, "e": 0.49}
    assert len(relevant(ranked(*sims), sims)) == 5


def test_new_or_off_topic_problem_returns_nothing():
    assert relevant(ranked("a", "b"), {"a": 0.37, "b": 0.31}) == []   # badge readers: loosely related at best
    assert relevant(ranked("a"), {"a": 0.11}) == []                   # weather
    assert RELEVANCE_MIN == 0.40


def test_rank_order_is_kept():
    sims = {"x": 0.50, "y": 0.55}
    assert [r for r, _ in relevant(ranked("x", "y"), sims)] == ["x", "y"]


def test_no_precedent_draft_is_a_plan_not_a_resolution():
    ticket = NS(summary="s", description="d", request_type=None, affected_service=None, business_entity=None,
                reporter=None, linked_issues=[], comments=[])
    cls = NS(service="Trade Matching", work_type="Incident", resolution="done")
    text = draft.draft_comment(ticket, cls, None, model=None)
    assert text.startswith("No matching past fix. Suggested first steps")
    assert "Resolution:" not in text


def test_follow_up_detection():
    from app.pipeline.copilot import is_follow_up

    assert is_follow_up("and who fixes it usually?")
    assert is_follow_up("How long does that take?")
    assert not is_follow_up("How do we fix the coffee machine badge reader on floor 3?")
    assert not is_follow_up("What does the Rimes Data Feed service cover for index providers?")
