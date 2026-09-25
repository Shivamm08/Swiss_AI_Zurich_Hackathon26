import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, nulls_last, or_, select
from sqlalchemy.orm import Session

from app import chat
from app.api.deps import get_actor, require_creator, require_manager
from app.db import get_db
from app.domain import priority_for, team_for
from app.ingest import jira_records, ticket_from_email, ticket_from_jira
from app.kb.learn import forget_resolution, learn_from_resolution
from app.pipeline import intake_check, llm
from app.models import Ticket, User
from app.schemas import (
    ActivityEntry,
    AssignRequest,
    EmailIngest,
    ImportResult,
    ReviewOut,
    TicketCreate,
    TicketNote,
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


def require_specialist(db: Session, email: str, team: str | None) -> User:
    """Work only goes to specialists, and only within the ticket's department."""
    user = db.get(User, email)
    if user is None or user.role != "specialist":
        raise HTTPException(status_code=400, detail=f"'{email}' is not a specialist. Tickets are dispatched to specialists only.")
    if team and team not in (user.teams or []):
        raise HTTPException(status_code=400, detail=f"{user.name} isn't in {team}. Change the service first to move the ticket to another department.")
    return user


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
    elif view == "inbox":  # the analyst's department: new AI proposals and tickets handed back to them
        stmt = stmt.where(Ticket.work_status == "open", Ticket.triage_state.in_(("proposed", "approved", "edited")),
                          Ticket.route != "triage")
        if not everyone:
            stmt = stmt.where(Ticket.ai_team.in_(my_teams))
    elif view == "team":
        stmt = stmt.where(Ticket.ai_team.in_(my_teams))
    elif view == "needs_review":
        stmt = stmt.where(needs_review)
    elif view == "escalations":
        stmt = stmt.where(Ticket.escalated.is_(True))
        if not everyone:  # an analyst's or specialist's own department
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
    """New-ticket form: Team Leads / Analysts and admins only. Jira import and email are the
    automatic intake channels."""
    creator = get_actor(db, body.created_by)
    require_creator(creator)
    screened = intake_check.check(body.summary, body.description, llm.resolve_model(None))
    if not screened.ok:
        raise HTTPException(status_code=422, detail=f"This doesn't look like a ticket: {screened.reason} "
                                                    "Describe what is broken or what you need, and for whom.")
    manual = body.manual.model_dump(exclude_none=True) if body.manual else {}
    if manual.get("assignee"):
        require_specialist(db, manual["assignee"], team_for(manual["service"]) if manual.get("service") else None)
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
    ticket = Ticket(**fields, raw=({"manual": manual} if manual else {}) | {"intake_check": screened.verdict})
    if manual.get("assignee"):  # only analysts and admins create tickets: choosing the specialist is their dispatch
        ticket.assignee, ticket.work_status = manual["assignee"], "assigned"
        ticket.add_activity(creator.email, "assigned", manual["assignee"])
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
    """Dispatch or reassign to a specialist: the department's Team Lead / Analyst or an admin."""
    ticket = get_ticket_or_404(db, ticket_id)
    require_manager(get_actor(db, body.by), ticket, "dispatch or reassign this ticket")
    if ticket.work_status == "done":
        raise HTTPException(status_code=409, detail="Ticket is already done")
    require_specialist(db, body.assignee, ticket.ai_team)
    ticket.assignee = body.assignee
    if ticket.work_status == "open":  # a human dispatched it: it leaves the analysts' queues
        ticket.work_status = "assigned"
        if ticket.route == "triage":
            ticket.route = "review"
    ticket.add_activity(body.by, "assigned", body.assignee)
    db.commit()
    db.refresh(ticket)
    return ticket


def notify_done(db: Session, ticket: Ticket) -> None:
    """Tell the department's Team Lead / Analyst that the work is finished: a direct message from the
    specialist with the resolution and closing note, linked to the ticket."""
    analysts = [u for u in db.scalars(select(User).where(User.role == "analyst")) if ticket.ai_team in (u.teams or [])]
    # A department without a Team Lead / Analyst falls back to the admin, who covers every department.
    analysts = analysts or list(db.scalars(select(User).where(User.role == "admin")))
    for analyst in analysts:
        if analyst.email != ticket.resolved_by:
            chat.post(db, chat.dm_channel(ticket.resolved_by, analyst.email), ticket.resolved_by,
                      f"Done: #{ticket.number} \"{ticket.summary}\" ({ticket.resolution}). {ticket.resolution_comment}",
                      kind="resolved", ticket_id=ticket.id)


# Allowed work transitions: action -> (from statuses, to status)
TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "start": (("assigned",), "in_progress"),
    "wait": (("assigned", "in_progress"), "waiting"),
    "resume": (("waiting",), "in_progress"),
    "resolve": (("assigned", "in_progress", "waiting"), "done"),
    "handback": (("assigned", "in_progress", "waiting"), "open"),  # back to the analyst to reassign
}


@router.post("/{ticket_id}/work", response_model=TicketOut)
def update_work(ticket_id: uuid.UUID, body: WorkUpdate, db: Session = Depends(get_db)) -> Ticket:
    """The specialist moves their ticket along. `resolve` closes it and adds it to the knowledge base;
    `handback` returns it to the department's analyst with a reason."""
    ticket = get_ticket_or_404(db, ticket_id)
    actor = get_actor(db, body.by)
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
    if body.action == "handback":
        if not (body.note or "").strip():
            raise HTTPException(status_code=422, detail="Say why you're handing it back, so the analyst can reassign it")
        chat.post(db, chat.team_channel(ticket.ai_team), actor.email,
                  f"Handing #{ticket.number} back for reassignment: {body.note.strip()}", kind="handoff", ticket_id=ticket.id)
        ticket.assignee = None
    ticket.work_status = target
    ticket.add_activity(body.by, body.action, note)
    if target == "done":
        if ticket.triage_results:
            learn_from_resolution(db, ticket)  # only finished work becomes knowledge
        notify_done(db, ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/reopen", response_model=TicketOut)
def reopen(ticket_id: uuid.UUID, body: TicketNote, db: Session = Depends(get_db)) -> Ticket:
    """The department's Team Lead / Analyst isn't satisfied with a done ticket: it goes back to the same
    specialist (assigned), its fix leaves the knowledge base, and the specialist gets a message."""
    ticket = get_ticket_or_404(db, ticket_id)
    actor = get_actor(db, body.by)
    require_manager(actor, ticket, "reopen this ticket")
    if ticket.work_status != "done":
        raise HTTPException(status_code=409, detail="Only a done ticket can be reopened")
    if not (body.note or "").strip():
        raise HTTPException(status_code=422, detail="Say what isn't right, so the specialist knows what to fix")
    specialist = ticket.resolved_by or ticket.assignee
    removed = forget_resolution(db, ticket)
    ticket.work_status, ticket.assignee = "assigned", specialist
    ticket.resolution = ticket.resolution_comment = ticket.resolved_at = ticket.resolved_by = None
    ticket.add_activity(actor.email, "reopened", body.note.strip())
    if specialist and specialist != actor.email:
        chat.post(db, chat.dm_channel(actor.email, specialist), actor.email,
                  f"Reopened #{ticket.number} \"{ticket.summary}\": {body.note.strip()}"
                  + (" (its fix was taken out of the knowledge base)" if removed else ""),
                  kind="reopened", ticket_id=ticket.id)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/deescalate", response_model=TicketOut)
def deescalate(ticket_id: uuid.UUID, body: TicketNote, db: Session = Depends(get_db)) -> Ticket:
    """The escalation is handled: the department's Team Lead / Analyst or an admin clears it."""
    ticket = get_ticket_or_404(db, ticket_id)
    require_manager(get_actor(db, body.by), ticket, "de-escalate this ticket")
    if not ticket.escalated:
        raise HTTPException(status_code=409, detail="Ticket is not escalated")
    ticket.escalated = False
    ticket.add_activity(body.by, "deescalated", body.note)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: uuid.UUID, by: str = Query(..., description="Admin email"), db: Session = Depends(get_db)) -> None:
    if get_actor(db, by).role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can delete tickets")
    ticket = get_ticket_or_404(db, ticket_id)
    forget_resolution(db, ticket)  # its fix must not outlive it in the knowledge base
    db.delete(ticket)
    db.commit()
