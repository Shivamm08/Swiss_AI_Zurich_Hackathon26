import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, nulls_last, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain import priority_for
from app.ingest import jira_records, ticket_from_email, ticket_from_jira
from app.kb.learn import learn_from_resolution
from app.models import Ticket, User
from app.schemas import (
    ActivityEntry,
    AssignRequest,
    EmailIngest,
    ImportResult,
    ReviewOut,
    TicketCreate,
    TicketDetail,
    TicketOut,
    TicketPage,
    TicketSource,
    TicketView,
    TriageResultOut,
    TriageState,
    WorkStatus,
    WorkUpdate,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_ticket_or_404(db: Session, ticket_id: uuid.UUID) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("", response_model=TicketPage)
def list_tickets(
    view: TicketView = Query("all", description="Queue tab"),
    as_user: str | None = Query(None, description="Email of the person viewing (for 'mine' / 'team')"),
    sort: str = Query("priority_score", pattern="^(priority_score|sla_due_at|number|confidence)$"),
    state: TriageState | None = None,
    work_status: WorkStatus | None = None,
    source: TicketSource | None = None,
    service: str | None = Query(None, description="AI service"),
    team: str | None = Query(None, description="AI team"),
    q: str | None = Query(None, description="Search summary and description"),
    include_done: bool = Query(False, description="Also list tickets that are done"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> TicketPage:
    stmt = select(Ticket)
    if not include_done and work_status != "done":
        stmt = stmt.where(Ticket.work_status != "done")
    user = db.get(User, as_user) if as_user else None
    my_teams = user.teams if user and user.teams else []
    everyone = user is None or user.role == "admin"
    # Waiting for an analyst: not triaged yet, or low confidence / rejected (the department may be wrong).
    needs_review = (Ticket.work_status == "open") & (
        (Ticket.triage_state == "new") | (Ticket.route == "triage") | (Ticket.triage_state == "rejected"))
    if view == "mine":
        stmt = stmt.where(Ticket.assignee == as_user, Ticket.work_status != "open")
    elif view == "inbox":  # AI proposals for the analyst's department, waiting for their decision
        stmt = stmt.where(Ticket.work_status == "open", Ticket.triage_state == "proposed", Ticket.route != "triage")
        if not everyone:
            stmt = stmt.where(Ticket.ai_team.in_(my_teams))
    elif view == "team":
        stmt = stmt.where(Ticket.ai_team.in_(my_teams))
    elif view == "needs_review":
        stmt = stmt.where(needs_review)
    elif view == "escalations":
        stmt = stmt.where(Ticket.escalated.is_(True))
        if not everyone and user.role == "analyst":
            stmt = stmt.where(Ticket.ai_team.in_(my_teams))
    if work_status:
        stmt = stmt.where(Ticket.work_status == work_status)
    if service:
        stmt = stmt.where(Ticket.ai_service == service)
    if team:
        stmt = stmt.where(Ticket.ai_team == team)
    if state:
        stmt = stmt.where(Ticket.triage_state == state)
    if source:
        stmt = stmt.where(Ticket.source == source)
    if q:
        stmt = stmt.where(or_(Ticket.summary.ilike(f"%{q}%"), Ticket.description.ilike(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = {
        "priority_score": [nulls_last(Ticket.priority_score.desc()), nulls_last(Ticket.sla_due_at.asc())],
        "sla_due_at": [nulls_last(Ticket.sla_due_at.asc())],
        "confidence": [nulls_last(Ticket.confidence.asc())],  # least confident first
        "number": [Ticket.number.desc()],
    }[sort]
    items = db.scalars(stmt.order_by(*order, Ticket.number.desc()).limit(limit).offset(offset)).all()
    return TicketPage(items=[TicketOut.model_validate(t) for t in items], total=total)


@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(body: TicketCreate, db: Session = Depends(get_db)) -> Ticket:
    manual = body.manual.model_dump(exclude_none=True) if body.manual else {}
    if manual.get("assignee") and db.get(User, manual["assignee"]) is None:
        raise HTTPException(status_code=400, detail=f"Unknown assignee '{manual['assignee']}'. See GET /api/users.")
    fields = body.model_dump(exclude={"manual", "created_by"})
    # Staff-confirmed values also become the ticket's intake values, so the UI shows them as received.
    fields.update({k: v for k, v in {
        "work_type": manual.get("work_type"),
        "affected_service": manual.get("service"),
        "urgency": manual.get("urgency"),
        "impact": manual.get("impact"),
    }.items() if v})
    if manual.get("urgency") and manual.get("impact"):
        fields["priority"] = priority_for(manual["urgency"], manual["impact"])
    ticket = Ticket(**fields, raw={"manual": manual} if manual else {})
    if manual.get("assignee"):  # only analysts and admins create tickets: choosing the specialist is their dispatch
        ticket.assignee, ticket.work_status = manual["assignee"], "assigned"
        ticket.add_activity(body.created_by or "staff", "assigned", manual["assignee"])
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/from-email", response_model=TicketOut, status_code=201)
def ingest_email(body: EmailIngest, db: Session = Depends(get_db)) -> Ticket:
    ticket = ticket_from_email(body.from_address, body.subject, body.body, body.business_entity)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/import", response_model=ImportResult)
def import_tickets(
    file: UploadFile = File(..., description="Jira export JSON (challenge or training format)"),
    source: TicketSource = Form("challenge"),
    db: Session = Depends(get_db),
) -> ImportResult:
    try:
        records = jira_records(json.load(file.file))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"File is not valid JSON: {exc}") from exc
    imported = skipped = 0
    for record in records:
        if not record.get("Summary"):
            skipped += 1
            continue
        db.add(ticket_from_jira(record, source))
        imported += 1
    db.commit()
    return ImportResult(imported=imported, skipped=skipped)


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)) -> TicketDetail:
    ticket = get_ticket_or_404(db, ticket_id)
    latest = ticket.triage_results[0] if ticket.triage_results else None
    return TicketDetail(
        **TicketOut.model_validate(ticket).model_dump(),
        latest_triage=TriageResultOut.model_validate(latest) if latest else None,
        reviews=[ReviewOut.model_validate(r) for r in ticket.reviews],
        activity=[ActivityEntry.model_validate(a) for a in reversed(ticket.activity or [])],
    )


@router.post("/{ticket_id}/assign", response_model=TicketOut)
def assign_ticket(ticket_id: uuid.UUID, body: AssignRequest, db: Session = Depends(get_db)) -> Ticket:
    """Dispatch or reassign to a specialist (analysts and admins)."""
    ticket = get_ticket_or_404(db, ticket_id)
    if db.get(User, body.assignee) is None:
        raise HTTPException(status_code=400, detail=f"Unknown user '{body.assignee}'. See GET /api/users.")
    if ticket.work_status == "done":
        raise HTTPException(status_code=409, detail="Ticket is already done")
    ticket.assignee = body.assignee
    if ticket.work_status == "open":  # a human dispatched it: it leaves the analysts' queues
        ticket.work_status = "assigned"
        if ticket.route == "triage":
            ticket.route = "review"
    ticket.add_activity(body.by or "analyst", "assigned", body.assignee)
    db.commit()
    db.refresh(ticket)
    return ticket


# Allowed work transitions: action -> (from statuses, to status)
TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "start": (("assigned",), "in_progress"),
    "wait": (("assigned", "in_progress"), "waiting"),
    "resume": (("waiting",), "in_progress"),
    "resolve": (("assigned", "in_progress", "waiting"), "done"),
}


@router.post("/{ticket_id}/work", response_model=TicketOut)
def update_work(ticket_id: uuid.UUID, body: WorkUpdate, db: Session = Depends(get_db)) -> Ticket:
    """The specialist moves their ticket along. `resolve` closes it and adds it to the knowledge base."""
    ticket = get_ticket_or_404(db, ticket_id)
    actor = db.get(User, body.by)
    if actor is None:
        raise HTTPException(status_code=400, detail=f"Unknown user '{body.by}'")
    if actor.email != ticket.assignee and actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only the assigned specialist (or an admin) can update the work")
    allowed, target = TRANSITIONS[body.action]
    if ticket.work_status not in allowed:
        raise HTTPException(status_code=409, detail=f"Can't {body.action} a ticket that is {ticket.work_status.replace('_', ' ')}")
    note = body.note
    if body.action == "resolve":
        if not body.resolution or not (body.resolution_comment or "").strip():
            raise HTTPException(status_code=422, detail="Resolving needs a resolution and a closing comment")
        ticket.resolution, ticket.resolution_comment = body.resolution, body.resolution_comment.strip()
        ticket.resolved_by, ticket.resolved_at = ticket.assignee, datetime.now(timezone.utc)
        note = body.resolution
    ticket.work_status = target
    ticket.add_activity(body.by, body.action, note)
    if target == "done" and ticket.triage_results:
        learn_from_resolution(db, ticket)  # only finished work becomes knowledge
    db.commit()
    db.refresh(ticket)
    return ticket


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    db.delete(get_ticket_or_404(db, ticket_id))
    db.commit()
