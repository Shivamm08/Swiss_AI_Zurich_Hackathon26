"""Simulated four-week desk history for demos: tickets, AI proposals, analyst reviews and chat.

Everything created here has source="demo" (tickets) or a deterministic demo id (messages), is
labelled "simulated" in the UI, and can be removed with --clear. The real challenge tickets and
anything people create are never touched.

How it is simulated (all numbers are assumptions, tuned to look like a normal service desk):
- tickets come from the training set's templates (no LLM calls), 6-14 per weekday;
- about 22% arrive with the wrong intake service (a sibling service or the generic email bucket);
- facts come from the ticket template, then the REAL rubric computes impact/urgency/priority;
- confidence depends on how clear the template is; routing uses the real thresholds;
- every ticket passes an analyst (the team lead): the more confident the proposal, the likelier it is
  approved as-is; a mild improvement over the four weeks stands in for the learning loop;
- approved tickets go to a specialist, who works them: everything older than 3 days is done, recent
  ones are assigned, in progress or waiting for information. Illustrative, not a measured result.

    python -m app.scripts.seed_demo             # (re)create the demo history
    python -m app.scripts.seed_demo --clear     # remove it
"""

import argparse
import json
import random
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import chat
from app.db import SessionLocal
from app.domain import LEVELS, SERVICE_CATALOG, TEAMS, normalize_level, priority_for, team_for
from app.models import KbDocument, Message, Review, Ticket, TriageResult, User
from app.pipeline import confidence, rubric
from app.schemas import Facts

TRAINING = Path("/data/jira_first_20000_requested_fields_synthetic.json")
DAYS = 28
DEMO_NS = uuid.UUID("5f0c6a9e-1d6b-4c1e-9d7a-7b1a2e0d0000")
GENERIC = "Emailed Support Tickets"

# template prefix -> (work type, facts, resolution weights, base confidence range)
TEMPLATES: dict[str, tuple[str, dict, dict, tuple[float, float]]] = {
    "Automated alert triggered for": ("Incident", dict(scope="one_entity", outage_extent="partial_degradation", workaround="none"),
                                      {"done": 0.75, "cannot reproduce": 0.2, "cancelled": 0.05}, (0.80, 0.97)),
    "External email warning received for": ("Incident", dict(scope="external_counterparty", outage_extent="partial_degradation", workaround="none"),
                                            {"done": 0.7, "cannot reproduce": 0.25, "cancelled": 0.05}, (0.70, 0.92)),
    "Operational issue reported for": ("Incident", dict(scope="one_entity", outage_extent="partial_degradation", workaround="difficult"),
                                       {"done": 0.85, "cannot reproduce": 0.15}, (0.75, 0.95)),
    "Incident mislabelled as service request in": ("Incident", dict(scope="team", outage_extent="partial_degradation", workaround="easy"),
                                                   {"done": 0.8, "cannot reproduce": 0.2}, (0.62, 0.88)),
    "Unclear incident input for": ("Incident", dict(scope="individual", outage_extent="partial_degradation", workaround="none"),
                                   {"clarification": 0.85, "cancelled": 0.15}, (0.22, 0.48)),
    "Email notification received for": ("Service Request", dict(scope="team", outage_extent="none", workaround="not_applicable"),
                                        {"done": 0.6, "cancelled": 0.4}, (0.60, 0.85)),
    "New license requested for": ("Service Request", dict(scope="individual", outage_extent="none", workaround="not_applicable"),
                                  {"done": 0.9, "cancelled": 0.1}, (0.85, 0.98)),
    "Access requested for": ("Service Request", dict(scope="individual", outage_extent="none", workaround="not_applicable"),
                             {"done": 0.9, "cancelled": 0.1}, (0.85, 0.98)),
    "Access removal requested for": ("Service Request", dict(scope="individual", outage_extent="none", workaround="not_applicable"),
                                     {"done": 0.92, "cancelled": 0.08}, (0.85, 0.98)),
    "General request for": ("Service Request", dict(scope="individual", outage_extent="none", workaround="not_applicable"),
                            {"clarification": 0.8, "cancelled": 0.2}, (0.30, 0.55)),
    "Incorrect incident title for service request in": ("Service Request", dict(scope="individual", outage_extent="none", workaround="not_applicable"),
                                                         {"done": 0.85, "cancelled": 0.15}, (0.60, 0.86)),
}

FALLBACK_COMMENT = {
    "done": "Resolution: Validated the reported behaviour on {service}, applied the standard remediation and confirmed normal operation with the reporter.",
    "clarification": "Resolution: Requested clarification from the reporter; the ticket does not state the affected {service} process, timeframe or expected outcome.",
    "cannot reproduce": "Resolution: Re-checked {service} logs and monitoring for the reported window; the symptom could not be reproduced.",
    "cancelled": "Resolution: Closed as no action required on {service}; the request was withdrawn or duplicated an existing ticket.",
}


def _demo_id(kind: str, i: int) -> uuid.UUID:
    return uuid.uuid5(DEMO_NS, f"{kind}-{i}")


def clear(db: Session) -> tuple[int, int]:
    tickets = db.scalars(select(Ticket.id).where(Ticket.source == "demo")).all()
    msgs = db.execute(delete(Message).where(Message.id.in_([_demo_id("msg", i) for i in range(5000)]))).rowcount
    db.execute(delete(Ticket).where(Ticket.source == "demo"))  # proposals + reviews cascade
    db.commit()
    return len(tickets), msgs or 0


def _act(ticket: Ticket, when: datetime, by: str | None, action: str, note: str | None) -> None:
    ticket.activity = [*(ticket.activity or []), {"at": when.isoformat(), "by": by or "analyst", "action": action, "note": note}]


def _pick(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def _shift(level: str, step: int) -> str:
    i = LEVELS.index(level) - step  # LEVELS runs Highest -> Lowest
    return LEVELS[min(max(i, 0), len(LEVELS) - 1)]


def seed(db: Session, rng: random.Random) -> dict[str, int]:
    records = [r for r in json.loads(TRAINING.read_text())
               if (r.get("Affected Business or IT Services") or [GENERIC])[0] != GENERIC]
    playbook = {d.meta["service"]: d for d in db.scalars(select(KbDocument).where(KbDocument.kind == "playbook"))}
    users = [u for u in db.scalars(select(User)) if u.role != "admin"]
    members = {t: [u.email for u in users if u.role == "specialist" and t in (u.teams or [])] for t in TEAMS}
    leads = {t: next((u.email for u in users if u.role == "analyst" and t in (u.teams or [])), None) for t in TEAMS}
    siblings = {s: [o for o in SERVICE_CATALOG if o != s and team_for(o) == team_for(s)] for s in SERVICE_CATALOG}
    today = datetime.now(timezone.utc).date()
    load: dict[str, int] = {u.email: 0 for u in users}
    made = {"tickets": 0, "reviews": 0, "messages": 0, "escalations": 0}
    escalated_refs: list[tuple[Ticket, str, datetime]] = []
    per_team_tickets: dict[str, list[Ticket]] = {t: [] for t in TEAMS}

    for back in range(DAYS - 1, -1, -1):
        day = today - timedelta(days=back)
        weekend = day.weekday() >= 5
        progress = (DAYS - 1 - back) / (DAYS - 1)  # 0 at the start, 1 today
        for _ in range(rng.randint(2, 5) if weekend else rng.randint(6, 14)):
            rec = rng.choice(records)
            true_service = rec["Affected Business or IT Services"][0]
            prefix = next((p for p in TEMPLATES if rec["Summary"].startswith(p)), "Operational issue reported for")
            work_type, base_facts, res_weights, (lo, hi) = TEMPLATES[prefix]
            created = datetime.combine(day, time(rng.randint(7, 18), rng.randint(0, 59)), tzinfo=timezone.utc)

            misrouted = rng.random() < 0.22
            intake_service = (rng.choice(siblings[true_service]) if siblings[true_service] and rng.random() < 0.5 else GENERIC) if misrouted else true_service
            intake_wt = ("Service Request" if work_type == "Incident" else "Incident") if "mislabel" in prefix or "Incorrect" in prefix else work_type

            clear_incident = work_type == "Incident" and prefix in (
                "Automated alert triggered for", "Operational issue reported for", "External email warning received for")
            facts = Facts(**base_facts,
                          regulatory_or_security=clear_incident and rng.random() < 0.04,
                          deadline_pressure="hard" if rng.random() < 0.08 else "soft" if rng.random() < 0.3 else "none")
            if clear_incident and rng.random() < 0.07:
                facts.outage_extent = "full_unavailability"
            age_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
            reviewed = back >= 1 or rng.random() < 0.45  # every ticket gets an analyst decision; today's partly pending
            done_by_now = back >= 3 or back == 2 and rng.random() < 0.5 or back == 1 and rng.random() < 0.15
            rub = rubric.apply_rubric(facts, true_service, work_type, age_days=age_days, resolved=reviewed and done_by_now)

            conf = rng.uniform(lo, hi) - (0.08 if misrouted else 0) + 0.04 * progress
            conf = round(min(max(conf, 0.12), 0.99), 3)
            route = confidence.route_for(conf)
            team = team_for(true_service)
            expert_doc = playbook.get(true_service)
            expert = expert_doc.meta["resolver"] if expert_doc else None
            pool = members[team] or [None]
            # like the real rule: the expert unless clearly busier than the least-loaded specialist
            least = min(pool, key=lambda p: load.get(p, 0) if p else 0)
            working = expert if expert in pool and load.get(expert, 0) <= load.get(least, 0) + 1 else least
            resolution = _pick(rng, res_weights)
            comment = (expert_doc.meta["note"] if expert_doc and resolution == "done" and rng.random() < 0.7
                       else FALLBACK_COMMENT[resolution].format(service=true_service))
            escalated = rub.priority == "Highest" and rub.critical

            ticket = Ticket(
                source="demo", work_type=intake_wt, request_type=None, summary=rec["Summary"], description=rec["Description"],
                affected_service=intake_service, business_entity=(rec.get("Business Entity") or [None])[0],
                reporter=rec.get("Reporter"), urgency=normalize_level(rec.get("Urgency")), impact=normalize_level(rec.get("Impact")),
                priority=normalize_level(rec.get("Priority")), status="open", linked_issues=[], comments=[], raw={"demo": True},
                triage_state="proposed", assignee=None, work_status="open", ai_service=true_service, ai_team=team, ai_priority=rub.priority,
                priority_score=rub.priority_score, confidence=conf, route=route, escalated=escalated,
                sla_due_at=confidence.sla_due(created, rub.priority), created_at=created, updated_at=created,
            )
            db.add(ticket)
            db.flush()
            triaged_at = created + timedelta(seconds=rng.randint(4, 40))
            result = TriageResult(
                ticket_id=ticket.id, work_type=work_type, service=true_service, team=team, assignee=expert,
                urgency=rub.urgency, impact=rub.impact, priority=rub.priority, resolution=resolution, resolution_comment=comment,
                confidence=conf, confidence_detail={"overall": conf, "votes": round(min(1, conf + 0.08), 3), "retrieval": conf,
                                                    "flags": ["unclear_input"] if resolution == "clarification" else []},
                facts=facts.model_dump(), priority_score=rub.priority_score, rubric_trace=rub.trace, vote_agreement={},
                route=route, escalated=escalated, sla_due_at=ticket.sla_due_at, assignee_suggestion=None,
                playbook_ref=expert_doc.ref_id if expert_doc else None, rationale="Simulated demo history.", evidence=[],
                changed_fields=[f for f, a, b in (("service", intake_service, true_service), ("work_type", intake_wt, work_type),
                                                  ("priority", ticket.priority, rub.priority)) if a and a != b],
                model="gpt-5.4-mini", latency_ms=rng.randint(2500, 9500), created_at=triaged_at,
            )
            db.add(result)
            db.flush()
            _act(ticket, triaged_at, chat.SYSTEM_SENDER, "triaged", f"{route} · {round(conf * 100)}% · gpt-5.4-mini")
            made["tickets"] += 1
            per_team_tickets[team].append(ticket)
            if escalated:
                made["escalations"] += 1
                escalated_refs.append((ticket, team, triaged_at))

            if reviewed:
                p_right = min(0.97, 0.22 + 0.74 * conf + 0.05 * progress)  # proposal is right as-is
                if rng.random() < p_right:
                    action = "approve" if rng.random() < 0.9 else "edit"  # sometimes only the wording is polished
                    light_edit = True
                else:
                    action = "reject" if rng.random() < 0.35 else "edit"
                    light_edit = False
                final = {"work_type": work_type, "service": true_service, "team": team, "assignee": expert,
                         "urgency": rub.urgency, "impact": rub.impact, "priority": rub.priority,
                         "resolution": resolution, "resolution_comment": comment}
                overridden: list[str] = []
                if action == "edit":
                    field = "resolution_comment" if light_edit else _pick(
                        rng, {"service": 0.3, "urgency": 0.35, "impact": 0.25, "assignee": 0.1} if conf < 0.6
                        else {"urgency": 0.45, "impact": 0.3, "assignee": 0.25})
                    if field in ("urgency", "impact"):
                        final[field] = _shift(final[field], rng.choice((-1, 1)))
                        final["priority"] = priority_for(final["urgency"], final["impact"])
                        overridden = [field] + (["priority"] if final["priority"] != rub.priority else [])
                    elif field == "service" and siblings[true_service]:
                        final["service"] = rng.choice(siblings[true_service])
                        overridden = ["service"]
                    elif field == "assignee" and len(pool) > 1:
                        final["assignee"] = rng.choice([p for p in pool if p != expert] or pool)
                        overridden = ["assignee"]
                    else:
                        final["resolution_comment"] = comment.replace("Resolution:", "Resolution (edited):")
                        overridden = ["resolution_comment"]
                reviewer = leads.get(team) or "admin@intcom.com"
                decided_at = triaged_at + timedelta(minutes=rng.randint(4, 150))
                db.add(Review(
                    ticket_id=ticket.id, triage_result_id=result.id, action=action,
                    final=final if action != "reject" else None, overridden_fields=overridden, reviewer=reviewer or "analyst",
                    review_seconds=round(rng.lognormvariate(4.1 - 0.35 * progress, 0.45), 1),
                    created_at=decided_at,
                ))
                made["reviews"] += 1
                ticket.triage_state = {"approve": "approved", "edit": "edited", "reject": "rejected"}[action]
                _act(ticket, decided_at, reviewer, ticket.triage_state, None)
                if action == "reject":
                    ticket.route = "triage"
                if action != "reject" or back >= 1:  # rejected ones are classified by hand, then dispatched
                    ticket.assignee = final["assignee"] if action == "edit" and "assignee" in overridden else working
                    ticket.work_status = "assigned"
                    if done_by_now:
                        ticket.work_status, ticket.resolution = "done", final["resolution"]
                        ticket.resolution_comment = final["resolution_comment"].replace("Resolution (edited):", "Resolution:")
                        ticket.resolved_by = ticket.assignee
                        ticket.resolved_at = min(decided_at + timedelta(hours=rng.uniform(0.5, 30)), datetime.now(timezone.utc) - timedelta(minutes=5))
                        _act(ticket, ticket.resolved_at, ticket.assignee, "resolve", ticket.resolution)
                    elif back >= 1 or rng.random() < 0.5:
                        ticket.work_status = _pick(rng, {"in_progress": 0.7, "waiting": 0.3})
            if ticket.assignee and ticket.work_status != "done":
                load[ticket.assignee] = load.get(ticket.assignee, 0) + 1

    made["messages"] = _seed_messages(db, rng, per_team_tickets, escalated_refs, members, leads, today)
    db.commit()
    return made


def _seed_messages(db: Session, rng: random.Random, per_team: dict[str, list[Ticket]], escalated: list,
                   members: dict[str, list[str]], leads: dict[str, str | None], today) -> int:
    lookup = chat.names(db)
    first = {e: n.split()[0] for e, n in lookup.items()}
    i = 0

    def add(channel: str, sender: str, body: str, when: datetime, kind: str = "message", ticket: Ticket | None = None) -> None:
        nonlocal i
        db.add(Message(id=_demo_id("msg", i), channel=channel, sender=sender, body=body, kind=kind,
                       ticket_id=ticket.id if ticket else None, created_at=when))
        i += 1

    def at(days_back: int, hour: int) -> datetime:
        return datetime.combine(today - timedelta(days=days_back), time(hour, rng.randint(0, 59)), tzinfo=timezone.utc)

    for ticket, team, when in escalated:
        who = first.get(ticket.assignee or "", "nobody yet")
        add(chat.team_channel(team), chat.SYSTEM_SENDER,
            f"Escalation: #{ticket.number} \"{ticket.summary}\" is Highest on {ticket.ai_service} (critical). "
            f"Assigned to {who}. Response due within 1 h.", when, "escalation", ticket)

    for team in TEAMS:
        people = members[team]
        if len(people) < 2:
            continue
        lead = leads[team] or people[0]
        others = [p for p in people if p != lead]
        tickets = per_team[team] or [None]
        services = [s for s, (t, _) in SERVICE_CATALOG.items() if t == team]
        ch = chat.team_channel(team)
        t1, t2, t3 = (rng.choice(tickets) for _ in range(3))
        a, b = rng.choice(others), rng.choice(people)
        replies = ["Taking it now.", "On it, I'll update the ticket within the hour.", "Mine. Vendor ticket already opened.",
                   "Picked up. The suggested fix looks right, I'll mark it done once verified.", "Assigned to me, thanks for flagging.",
                   "Looking now; looks like the same mapping issue as last week."]
        fyis = ["FYI the fix from #{n} worked again today; Copilot suggested it straight away.",
                "Closed #{n} with the suggested resolution, confirmed with the desk.",
                "#{n} was misrouted to us at intake, the AI caught it and moved it. Nice.",
                "Note for everyone: #{n} is the reference case for this kind of alert now."]
        script = [
            (26, 8, lead, f"Morning team. New triage flow is live: the AI proposes, I check and dispatch, you resolve. Please mark tickets done with a proper closing note, that's what the Copilot learns from.", "message", None),
            (21, 10, a, f"Vendor maintenance on {rng.choice(services)} tonight 22:00-23:00 CET. Expect alerts; they will be auto-routed to us.", "message", None),
            (17, 14, b, f"Handing #{t1.number if t1 else '—'} back for reassignment: at capacity until the change window is done.", "handoff", t1),
            (17, 14, lead, f"Reassigned to {first.get(a, 'a colleague')}. Thanks for flagging early.", "message", None),
            (17, 15, a, "On it. The suggested fix matches what we did last month.", "message", None),
            (11, 9, lead, f"Nice work this week: fewer tickets bounced to other teams. Keep writing specific closing notes, the AI learns from every ticket you close.", "message", None),
            (6, 16, rng.choice(others), rng.choice(fyis).format(n=t2.number if t2 else '—'), "message", t2),
            (2, 11, lead, f"Dispatched #{t3.number if t3 else '—'} to the team, it's on the SLA clock. Shout if you're at capacity.", "message", t3),
            (1, 15, rng.choice(others), rng.choice(replies), "message", None),
        ]
        for days_back, hour, sender, body, kind, ticket in script:
            add(ch, sender, body, at(days_back, hour), kind, ticket)

    # Direct messages: analysts (team leads) with their specialists, and the admin with a few leads.
    pairs = []
    for team in rng.sample(TEAMS, 5):
        lead, others = leads[team], [p for p in members[team] if p != leads[team]]
        if lead and others:
            pairs.append((lead, rng.choice(others), team))
    for sender, receiver, team in pairs:
        ch = chat.dm_channel(sender, receiver)
        tk = rng.choice(per_team[team]) if per_team[team] else None
        add(ch, sender, f"Hi {first.get(receiver, '')}, I've dispatched #{tk.number if tk else '—'} to you: priority went up after triage.", at(3, 9), "message", tk)
        add(ch, receiver, "Yes, picking it up. The suggested resolution looks right, I'll mark it done once it's verified.", at(3, 9))
        add(ch, sender, "Great, thanks. Ping me if you need the vendor contact.", at(3, 10))
    admin = "admin@intcom.com"
    for team in rng.sample(TEAMS, 3):
        if leads[team]:
            ch = chat.dm_channel(admin, leads[team])
            add(ch, admin, f"Quick check on {team}: workload looks uneven this week. Can you rebalance using the Team workload view?", at(4, 13))
            add(ch, leads[team], "Done. Moved two tickets to the colleague with most capacity.", at(4, 15))
    return i


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="only remove the demo history")
    args = parser.parse_args()
    with SessionLocal() as db:
        tickets, msgs = clear(db)
        print(f"Removed {tickets} demo tickets and {msgs} demo messages")
        if not args.clear:
            made = seed(db, random.Random(20260925))
            print("Created " + ", ".join(f"{v} {k}" for k, v in made.items()))


if __name__ == "__main__":
    main()
