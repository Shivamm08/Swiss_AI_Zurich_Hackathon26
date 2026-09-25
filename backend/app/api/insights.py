from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.domain import normalize_level
from app.models import KbDocument, Review, Ticket, TriageResult, User
from app.pipeline.assignment import is_open
from app.domain import LEVELS
from app.schemas import Calibration, CalibrationBucket, ChallengeStats, DailyPoint, Impact, Metrics, TicketSource

router = APIRouter(tags=["insights"])


@router.get("/metrics", response_model=Metrics)
def get_metrics(db: Session = Depends(get_db)) -> Metrics:
    by_state = {s: 0 for s in ("new", "proposed", "approved", "edited", "rejected")}
    for state, count in db.execute(select(Ticket.triage_state, func.count()).group_by(Ticket.triage_state)):
        by_state[state] = count

    reviews = db.scalars(select(Review)).all()
    actions = Counter(r.action for r in reviews)
    total = len(reviews)
    rate = (lambda n: round(n / total, 3) if total else None)
    times = [r.review_seconds for r in reviews if r.review_seconds is not None]
    overrides = Counter(f for r in reviews for f in r.overridden_fields)
    tickets = db.scalars(select(Ticket)).all()
    active = [t for t in tickets if is_open(t)]
    now = datetime.now(timezone.utc)

    return Metrics(
        tickets_total=sum(by_state.values()),
        by_state=by_state,
        reviews_total=total,
        acceptance_rate=rate(actions["approve"]),
        edit_rate=rate(actions["edit"]),
        reject_rate=rate(actions["reject"]),
        avg_review_seconds=round(sum(times) / len(times), 1) if times else None,
        avg_confidence=db.scalar(select(func.avg(TriageResult.confidence))),
        field_override_counts=dict(overrides),
        by_route=dict(Counter(t.route for t in tickets if t.route)),
        escalations_open=sum(1 for t in active if t.escalated),
        sla_breaches=sum(1 for t in active if t.sla_due_at and t.sla_due_at < now),
        priority_intake=dict(Counter(t.priority for t in tickets if t.priority)),
        priority_ai=dict(Counter(t.ai_priority for t in tickets if t.ai_priority)),
    )


@router.get("/metrics/calibration", response_model=Calibration)
def get_calibration(db: Session = Depends(get_db)) -> Calibration:
    """Does confidence mean something? Per confidence bucket, the share of reviewed proposals
    that analysts accepted without changing service or priority."""
    edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0001]
    rows = db.execute(select(TriageResult.confidence, Review.action, Review.overridden_fields)
                      .join(Review, Review.triage_result_id == TriageResult.id))
    stats = [[0, 0] for _ in range(len(edges) - 1)]
    for conf, action, overridden in rows:
        i = next(i for i in range(len(edges) - 1) if edges[i] <= conf < edges[i + 1])
        stats[i][0] += 1
        stats[i][1] += action != "reject" and not {"service", "priority"} & set(overridden or [])
    return Calibration(
        buckets=[CalibrationBucket(low=edges[i], high=min(edges[i + 1], 1.0), reviewed=n,
                                   agreement=round(ok / n, 3) if n else None) for i, (n, ok) in enumerate(stats)],
        note="Agreement with analyst reviews; replace with evaluation-set accuracy once available.",
    )


@router.get("/export/submission", response_model=list[dict[str, Any]])
def export_submission(source: TicketSource = "challenge", db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Challenge-format records with our decisions filled in.
    Uses the analyst-approved/edited decision when there is one, else the latest AI proposal; a
    ticket that is done uses the specialist's actual resolution and closing comment.
    TODO: confirm the exact expected submission format with Swiss Life."""
    records = []
    for ticket in db.scalars(select(Ticket).where(Ticket.source == source).order_by(Ticket.number)):
        decision = next((r.final for r in ticket.reviews if r.final), None)
        if decision is None and ticket.triage_results:
            latest = ticket.triage_results[0]
            decision = {f: getattr(latest, f) for f in (
                "work_type", "service", "team", "assignee", "urgency",
                "impact", "priority", "resolution", "resolution_comment",
            )}
        record = dict(ticket.raw)
        if decision and ticket.work_status == "done" and ticket.resolution_comment:
            decision = {**decision, "resolution": ticket.resolution, "resolution_comment": ticket.resolution_comment}
        if decision:
            record.update({
                "Work type": decision["work_type"],
                "Affected Business or IT Services": [decision["service"]],
                "Service Team(s)": [decision["team"]],
                "Assignee": decision["assignee"],
                "Urgency": decision["urgency"],
                "Impact": decision["impact"],
                "Priority": decision["priority"],
                "Resolution": decision["resolution"],
                "Resolution comment": decision["resolution_comment"],
                "All Comments": [*ticket.comments, f"{decision['assignee'] or 'agent'}: {decision['resolution_comment']}"],
            })
        records.append(record)
    return records


@router.get("/metrics/challenge", response_model=ChallengeStats)
def get_challenge_stats(source: TicketSource = "challenge", db: Session = Depends(get_db)) -> ChallengeStats:
    """Coverage and certainty on the challenge tickets (the answer set is hidden, so no accuracy)."""
    tickets = db.scalars(select(Ticket).where(Ticket.source == source)).all()
    latest = [t.triage_results[0] for t in tickets if t.triage_results]
    reviews = [r for t in tickets for r in t.reviews]
    avg = (lambda xs: round(sum(xs) / len(xs), 3) if xs else None)
    rank = {level: i for i, level in enumerate(LEVELS)}  # Highest = 0
    by_id = {t.id: t for t in tickets}
    moved = [(rank[p], rank[r.priority]) for r in latest if (p := normalize_level(by_id[r.ticket_id].priority))]
    votes = [sum(r.vote_agreement.values()) / len(r.vote_agreement) for r in latest if r.vote_agreement]
    return ChallengeStats(
        tickets=len(tickets),
        triaged=len(latest),
        heuristic=sum(1 for r in latest if r.model == "heuristic"),
        avg_confidence=avg([r.confidence for r in latest]),
        avg_vote_agreement=avg(votes),
        unanimous_service=sum(1 for r in latest if r.vote_agreement.get("service") == 1.0),
        with_precedent=sum(1 for r in latest if r.playbook_ref and not r.playbook_ref.startswith("svc-")),
        by_route=dict(Counter(r.route for r in latest if r.route)),
        by_priority={lvl: n for lvl in LEVELS if (n := sum(1 for r in latest if r.priority == lvl))},
        by_service=dict(Counter(r.service for r in latest).most_common()),
        changed_vs_intake=dict(Counter(f for r in latest for f in r.changed_fields)),
        priority_raised=sum(1 for before, after in moved if after < before),
        priority_lowered=sum(1 for before, after in moved if after > before),
        escalated=sum(1 for r in latest if r.escalated),
        avg_latency_seconds=avg([r.latency_ms / 1000 for r in latest]),
        decided=len(reviews),
        accepted_unchanged=sum(1 for r in reviews if r.action == "approve"),
        note="No answer labels are available (hidden set): this shows coverage, certainty and changes versus intake, not accuracy.",
    )


KPI_FIELDS = ("work_type", "service", "urgency", "impact", "priority", "assignee", "resolution")
DISPATCH = {"approved", "edited", "assigned"}


def desk_kpis(tickets: list[Ticket], reviews: list[Review]) -> dict[str, Any]:
    """Time to assign, first-time accuracy (per field), AI misroutes, reassignments and reopens."""
    def when(entry: dict) -> datetime:
        return datetime.fromisoformat(entry["at"])

    waits, dispatched, reassigned = [], 0, 0
    done_or_reopened, reopened = 0, 0
    for t in tickets:
        log = t.activity or []
        steps = [i for i, a in enumerate(log) if a.get("action") in DISPATCH]
        if steps:
            dispatched += 1
            waits.append((when(log[steps[0]]) - t.created_at).total_seconds() / 60)
            later = log[steps[0] + 1:]
            reassigned += any(a.get("action") in ("assigned", "handback") for a in later)
        was_reopened = any(a.get("action") == "reopened" for a in log)
        reopened += was_reopened
        done_or_reopened += t.work_status == "done" or was_reopened
    decided = len(reviews)
    ratio = (lambda n, d: round(n / d, 3) if d else None)
    waits.sort()
    return {
        "time_to_assign_minutes": round(waits[len(waits) // 2], 1) if waits else None,
        "first_time_accuracy": ratio(sum(1 for r in reviews if r.action == "approve"), decided),
        "field_accuracy": {f: round(1 - sum(1 for r in reviews if f in (r.overridden_fields or [])) / decided, 3)
                           for f in KPI_FIELDS} if decided else {},
        "ai_misroute_rate": ratio(sum(1 for r in reviews if r.action == "reject" or "service" in (r.overridden_fields or [])), decided),
        "reassignment_rate": ratio(reassigned, dispatched),
        "reopen_rate": ratio(reopened, done_or_reopened),
    }


@router.get("/metrics/impact", response_model=Impact)
def get_impact(
    include_demo: bool = True,
    days: int = 28,
    db: Session = Depends(get_db),
) -> Impact:
    """Business view: the service-desk pain points and how much of each the system handled."""
    tickets = [t for t in db.scalars(select(Ticket)) if include_demo or t.source != "demo"]
    ids = {t.id for t in tickets}
    results = [r for r in db.scalars(select(TriageResult).order_by(TriageResult.created_at)) if r.ticket_id in ids]
    latest = {r.ticket_id: r for r in results}  # ordered by time, so the last one wins
    reviews = [r for r in db.scalars(select(Review)) if r.ticket_id in ids]
    by_id = {t.id: t for t in tickets}

    def misrouted(r: TriageResult) -> bool:
        intake = by_id[r.ticket_id].affected_service
        return bool(intake) and intake != r.service

    routed = [r.route for r in latest.values() if r.route]
    actions = Counter(r.action for r in reviews)
    review_secs = [r.review_seconds for r in reviews if r.review_seconds is not None]
    triage_secs = [r.latency_ms / 1000 for r in latest.values()]
    minutes_saved = max(0.0, len(latest) * settings.manual_triage_minutes - sum(review_secs) / 60)

    # Workload balance: open tickets per person against their capacity.
    capacity = {u.email: u.capacity or settings.default_capacity for u in db.scalars(select(User)) if u.role != "admin"}
    open_per = Counter(t.assignee for t in tickets if t.assignee and is_open(t))
    loads = [open_per[p] / c for p, c in capacity.items() if c]

    start = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    buckets: dict[str, dict] = {
        (start + timedelta(days=i)).isoformat(): defaultdict(int) | {"review_secs": []} for i in range(days)
    }
    for t in tickets:
        if (d := t.created_at.date().isoformat()) in buckets:
            buckets[d]["created"] += 1
    for r in results:
        if (d := r.created_at.date().isoformat()) in buckets:
            b = buckets[d]
            b["triaged"] += 1
            b[r.route or "review"] += 1
            b["misroutes"] += misrouted(r)
    for rv in reviews:
        if (d := rv.created_at.date().isoformat()) in buckets:
            b = buckets[d]
            b[{"approve": "approved", "edit": "edited", "reject": "rejected"}[rv.action]] += 1
            if rv.review_seconds is not None:
                b["review_secs"].append(rv.review_seconds)
    points = []
    for day, b in buckets.items():
        reviewed = b["approved"] + b["edited"] + b["rejected"]
        points.append(DailyPoint(
            day=day, created=b["created"], triaged=b["triaged"], approved=b["approved"], edited=b["edited"],
            rejected=b["rejected"], auto=b["auto"], review=b["review"], triage=b["triage"], misroutes=b["misroutes"],
            avg_review_seconds=round(sum(b["review_secs"]) / len(b["review_secs"]), 1) if b["review_secs"] else None,
            acceptance_rate=round(b["approved"] / reviewed, 3) if reviewed else None,
        ))

    return Impact(
        **desk_kpis(tickets, reviews),
        include_demo=include_demo,
        tickets=len(tickets),
        tickets_triaged=len(latest),
        misroutes_caught=sum(1 for r in latest.values() if misrouted(r)),
        priority_corrected=sum(1 for r in latest.values()
                               if (p := normalize_level(by_id[r.ticket_id].priority)) and p != r.priority),
        clarifications_requested=sum(1 for r in latest.values() if r.resolution == "clarification"),
        escalations=sum(1 for t in tickets if t.escalated),
        auto_routed_share=round(routed.count("auto") / len(routed), 3) if routed else None,
        acceptance_rate=round(actions["approve"] / len(reviews), 3) if reviews else None,
        avg_triage_seconds=round(sum(triage_secs) / len(triage_secs), 1) if triage_secs else None,
        avg_review_seconds=round(sum(review_secs) / len(review_secs), 1) if review_secs else None,
        minutes_saved=round(minutes_saved),
        manual_triage_minutes=settings.manual_triage_minutes,
        max_load=round(max(loads), 3) if loads else None,
        over_capacity=sum(1 for load in loads if load >= 1),
        learned_documents=db.scalar(select(func.count()).select_from(KbDocument).where(KbDocument.kind == "historical_ticket")) or 0,
        days=points,
    )
