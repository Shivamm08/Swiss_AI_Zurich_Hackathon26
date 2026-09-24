import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.tickets import get_ticket_or_404
from app.db import get_db
from app.domain import priority_for, team_for
from app.models import Review, Ticket, TriageResult
from app.pipeline.pipeline import run_triage
from app.schemas import (
    BatchTriageRequest,
    BatchTriageResult,
    Decision,
    ReviewCreate,
    ReviewOut,
    TriageResultOut,
)

router = APIRouter(tags=["triage"])

_STATE_FOR_ACTION = {"approve": "approved", "edit": "edited", "reject": "rejected"}


@router.post("/tickets/{ticket_id}/triage", response_model=TriageResultOut)
def triage_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)) -> TriageResult:
    return run_triage(db, get_ticket_or_404(db, ticket_id))


@router.post("/triage/batch", response_model=BatchTriageResult)
def triage_batch(body: BatchTriageRequest, db: Session = Depends(get_db)) -> BatchTriageResult:
    stmt = select(Ticket)
    if body.ticket_ids:
        stmt = stmt.where(Ticket.id.in_(body.ticket_ids))
    else:
        stmt = stmt.where(Ticket.triage_state == "new")
    if body.source:
        stmt = stmt.where(Ticket.source == body.source)
    triaged = failed = 0
    for ticket in db.scalars(stmt).all():
        try:
            run_triage(db, ticket)
            triaged += 1
        except Exception:
            db.rollback()
            failed += 1
    return BatchTriageResult(triaged=triaged, failed=failed)


@router.get("/triage/{result_id}", response_model=TriageResultOut)
def get_triage_result(result_id: uuid.UUID, db: Session = Depends(get_db)) -> TriageResult:
    result = db.get(TriageResult, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Triage result not found")
    return result


@router.post("/triage/{result_id}/review", response_model=ReviewOut, status_code=201)
def review_triage(result_id: uuid.UUID, body: ReviewCreate, db: Session = Depends(get_db)) -> Review:
    result = db.get(TriageResult, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Triage result not found")

    proposed = Decision.model_validate(result, from_attributes=True)
    final: Decision | None = None
    overridden: list[str] = []
    if body.action == "approve":
        final = proposed
    elif body.action == "edit":
        edits = body.edits.model_dump(exclude_unset=True) if body.edits else {}
        merged = proposed.model_dump() | edits
        merged["team"] = team_for(merged["service"])
        merged["priority"] = priority_for(merged["urgency"], merged["impact"])
        final = Decision.model_validate(merged)
        overridden = [f for f, v in final.model_dump().items() if v != getattr(proposed, f)]

    review = Review(
        ticket_id=result.ticket_id,
        triage_result_id=result.id,
        action=body.action,
        final=final.model_dump() if final else None,
        overridden_fields=overridden,
        reviewer=body.reviewer,
        notes=body.notes,
        review_seconds=body.review_seconds,
    )
    db.add(review)
    result.ticket.triage_state = _STATE_FOR_ACTION[body.action]
    db.commit()
    db.refresh(review)
    return review
