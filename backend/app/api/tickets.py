import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingest import jira_records, ticket_from_email, ticket_from_jira
from app.models import Ticket
from app.schemas import (
    EmailIngest,
    ImportResult,
    ReviewOut,
    TicketCreate,
    TicketDetail,
    TicketOut,
    TicketPage,
    TicketSource,
    TriageResultOut,
    TriageState,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_ticket_or_404(db: Session, ticket_id: uuid.UUID) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("", response_model=TicketPage)
def list_tickets(
    state: TriageState | None = None,
    source: TicketSource | None = None,
    q: str | None = Query(None, description="Search summary and description"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> TicketPage:
    stmt = select(Ticket)
    if state:
        stmt = stmt.where(Ticket.triage_state == state)
    if source:
        stmt = stmt.where(Ticket.source == source)
    if q:
        stmt = stmt.where(or_(Ticket.summary.ilike(f"%{q}%"), Ticket.description.ilike(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Ticket.number.desc()).limit(limit).offset(offset)).all()
    return TicketPage(items=[TicketOut.model_validate(t) for t in items], total=total)


@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(body: TicketCreate, db: Session = Depends(get_db)) -> Ticket:
    ticket = Ticket(**body.model_dump(), raw={})
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
    )


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    db.delete(get_ticket_or_404(db, ticket_id))
    db.commit()
