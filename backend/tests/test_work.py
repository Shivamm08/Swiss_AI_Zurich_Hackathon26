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
