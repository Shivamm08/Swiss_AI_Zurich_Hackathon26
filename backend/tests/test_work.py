from app.api.tickets import TRANSITIONS
from app.pipeline.assignment import ACTIVE_WORK


def test_every_active_status_can_reach_done():
    for status in ACTIVE_WORK:
        assert status in TRANSITIONS["resolve"][0]


def test_work_only_moves_forward_from_dispatch():
    # A specialist can't pick up a ticket the analyst hasn't dispatched, or reopen a done one.
    for allowed, _ in TRANSITIONS.values():
        assert "open" not in allowed and "done" not in allowed


def test_waiting_goes_back_to_in_progress():
    assert TRANSITIONS["wait"][1] == "waiting"
    assert TRANSITIONS["resume"] == (("waiting",), "in_progress")


def test_handback_returns_work_to_the_analyst():
    assert TRANSITIONS["handback"] == (("assigned", "in_progress", "waiting"), "open")


# ---- who may do what (plain objects stand in for rows)
from types import SimpleNamespace as NS  # noqa: E402

from app.api.deps import can_escalate, can_manage  # noqa: E402

ANALYST = NS(email="lead@x.com", role="analyst", teams=["Client Services"])
OTHER_ANALYST = NS(email="other@x.com", role="analyst", teams=["Tax & Reporting"])
SPECIALIST = NS(email="spec@x.com", role="specialist", teams=["Client Services"])
ADMIN = NS(email="admin@x.com", role="admin", teams=[])


def ticket(**kw):
    base = dict(ai_team="Client Services", work_status="assigned", triage_state="approved", route="review", assignee="spec@x.com")
    return NS(**(base | kw))


def test_analysts_manage_only_their_department():
    assert can_manage(ANALYST, ticket())
    assert not can_manage(OTHER_ANALYST, ticket())
    assert can_manage(ADMIN, ticket())
    assert not can_manage(SPECIALIST, ticket())


def test_needs_review_pool_is_shared_by_all_analysts():
    pooled = ticket(work_status="open", route="triage", assignee=None)
    assert can_manage(OTHER_ANALYST, pooled)
    assert not can_manage(SPECIALIST, pooled)


def test_escalation_rights():
    assert can_escalate(SPECIALIST, ticket())                        # the specialist on it
    assert not can_escalate(SPECIALIST, ticket(assignee="someone@x.com"))
    assert can_escalate(ANALYST, ticket()) and can_escalate(ADMIN, ticket())
    assert not can_escalate(OTHER_ANALYST, ticket())


def test_roster_has_exactly_one_team_lead_per_department():
    import yaml

    from app.config import settings
    from app.domain import TEAMS

    roster = yaml.safe_load((settings.kb_dir / "roster.yaml").read_text())
    for team in TEAMS:
        leads = [p["email"] for p in roster if p["role"] == "analyst" and team in p["teams"]]
        specialists = [p["email"] for p in roster if p["role"] == "specialist" and team in p["teams"]]
        assert len(leads) == 1, f"{team} needs exactly one Team Lead / Analyst, has {leads}"
        assert specialists, f"{team} has no specialists to dispatch to"
