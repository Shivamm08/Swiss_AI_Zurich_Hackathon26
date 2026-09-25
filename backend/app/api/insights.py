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
from app.schemas import Calibration, CalibrationBucket, DailyPoint, Impact, Metrics, TicketSource

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
