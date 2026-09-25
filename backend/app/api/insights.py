from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Review, Ticket, TriageResult
from app.schemas import Calibration, CalibrationBucket, Metrics, TicketSource

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
    active = [t for t in tickets if t.triage_state in ("proposed", "approved", "edited")]
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
    Uses the analyst-approved/edited decision when there is one, else the latest AI proposal.
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
