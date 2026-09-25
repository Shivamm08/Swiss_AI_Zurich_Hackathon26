from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

from app.api.insights import desk_kpis
from app.pipeline.intake_check import _looks_like_text, check


def test_rules_reject_gibberish_and_symbols():
    assert _looks_like_text("asdkjh qweqwe\nzzzzz xxxxx")
    assert _looks_like_text("!!!! 1234 ####\n$$$ %%% 999")


def test_rules_accept_real_and_vague_tickets():
    assert _looks_like_text("Cash not there pls fix asap\nfor yesterday margin sweep") is None
    assert _looks_like_text("SCD_POS_SYNC failed on EAPW8504\nSimCorp replication job failed overnight") is None


def test_without_a_model_only_rules_decide():
    assert check("Laptop", "my laptop is broken", model=None).ok
    assert not check("asdf", "qwer", model=None).ok


def at(minutes):
    return (datetime(2026, 9, 1, 8, tzinfo=timezone.utc) + timedelta(minutes=minutes)).isoformat()


def test_desk_kpis():
    t0 = datetime(2026, 9, 1, 8, tzinfo=timezone.utc)
    tickets = [
        NS(created_at=t0, work_status="done", activity=[{"action": "approved", "at": at(30)}, {"action": "resolve", "at": at(90)}]),
        NS(created_at=t0, work_status="assigned", activity=[{"action": "approved", "at": at(10)}, {"action": "handback", "at": at(20)},
                                                          {"action": "assigned", "at": at(25)}]),
        NS(created_at=t0, work_status="done", activity=[{"action": "edited", "at": at(50)}, {"action": "resolve", "at": at(60)},
                                                      {"action": "reopened", "at": at(70)}, {"action": "resolve", "at": at(80)}]),
        NS(created_at=t0, work_status="open", activity=[]),
    ]
    reviews = [NS(action="approve", overridden_fields=[]), NS(action="edit", overridden_fields=["service", "urgency"]),
               NS(action="reject", overridden_fields=[]), NS(action="approve", overridden_fields=[])]
    k = desk_kpis(tickets, reviews)
    assert k["time_to_assign_minutes"] == 30.0          # median of 10, 30, 50
    assert k["first_time_accuracy"] == 0.5
    assert k["ai_misroute_rate"] == 0.5                  # one service change + one reject
    assert k["field_accuracy"]["service"] == 0.75
    assert k["reassignment_rate"] == round(1 / 3, 3)
    assert k["reopen_rate"] == 0.5
