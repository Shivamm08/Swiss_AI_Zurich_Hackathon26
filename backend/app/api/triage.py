import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import validate_model
from app.api.tickets import get_ticket_or_404
from app.db import SessionLocal, get_db
from app.domain import priority_for, team_for
from app.models import Review, Ticket, TriageResult, User
from app.pipeline import assignment
from app.pipeline.pipeline import run_triage, triage_events
from app.pipeline.rubric import is_critical, rescore
from app.schemas import (
    BatchTriageRequest,
    BatchTriageResult,
    Decision,
    ReviewCreate,
    ReviewOut,
    TriageRequest,
    TriageResultOut,
    TriageStreamEvent,
)

router = APIRouter(tags=["triage"])


def _dispatch_to(db: Session, ticket: Ticket, result: TriageResult, final: Decision, chosen: str | None) -> str | None:
    """Who gets the work: the analyst's pick, else the AI's recommendation (re-computed if the
    analyst moved the ticket to another team)."""
    if chosen and db.get(User, chosen):
        return chosen
    recommended = (result.assignee_suggestion or {}).get("recommended")
    person = db.get(User, recommended) if recommended else None
    if final.team == result.team and person and person.role == "specialist":
        return recommended
    return assignment.suggest(db, final.team, final.service, None, ticket_id=ticket.id).recommended

_STATE_FOR_ACTION = {"approve": "approved", "edit": "edited", "reject": "rejected"}


@router.post("/tickets/{ticket_id}/triage", response_model=TriageResultOut)
def triage_ticket(
    ticket_id: uuid.UUID, body: TriageRequest | None = None, db: Session = Depends(get_db)
) -> TriageResult:
    model = validate_model(body.model if body else None)
    return run_triage(db, get_ticket_or_404(db, ticket_id), model)


@router.get(
    "/tickets/{ticket_id}/triage/stream",
    response_class=StreamingResponse,
    responses={200: {"model": TriageStreamEvent, "content": {"text/event-stream": {}},
                     "description": "Server-sent events, one TriageStreamEvent per stage"}},
)
def stream_triage(
    ticket_id: uuid.UUID,
    model: str | None = Query(None, description="Model from /api/llm/models, or 'heuristic'"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Live walkthrough: runs the pipeline and streams each stage as it happens."""
    model = validate_model(model)
    get_ticket_or_404(db, ticket_id)

    def events():
        # Own session: the request-scoped one may close before the stream ends.
        with SessionLocal() as session:
            ticket = session.get(Ticket, ticket_id)
            try:
                for event in triage_events(session, ticket, model):
                    yield f"data: {event.model_dump_json()}\n\n"
            except Exception as exc:  # surface failures in the walkthrough instead of a broken stream
                session.rollback()
                failed = TriageStreamEvent(stage="error", status="failed", elapsed_ms=0,
                                           message=f"Triage failed: {type(exc).__name__}", data={"detail": str(exc)[:500]})
                yield f"data: {failed.model_dump_json()}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/triage/batch", response_model=BatchTriageResult)
def triage_batch(body: BatchTriageRequest, db: Session = Depends(get_db)) -> BatchTriageResult:
    model = validate_model(body.model)
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
            run_triage(db, ticket, model)
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
    """The analyst's decision on the AI proposal. Approve/edit dispatches the ticket to a specialist;
    reject sends it to Needs review. (The knowledge base learns later, when the work is done.)"""
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
    ticket = result.ticket
    ticket.triage_state = _STATE_FOR_ACTION[body.action]
    if final is not None:
        # Keep the queue in sync with the human decision.
        ticket.ai_service, ticket.ai_team = final.service, final.team
        ticket.priority_score = rescore(result.priority, ticket.priority_score, final.priority)
        ticket.ai_priority = final.priority
        ticket.escalated = final.priority == "Highest" and is_critical(final.service)
        if ticket.route == "triage":
            ticket.route = "review"
        if ticket.work_status in ("open", "assigned"):  # not started yet: (re)dispatch
            ticket.assignee = _dispatch_to(db, ticket, result, final, body.edits.assignee if body.edits else None)
            ticket.work_status = "assigned" if ticket.assignee else "open"
    elif ticket.work_status in ("open", "assigned"):  # rejected: Needs review, for an analyst to classify by hand
        ticket.route, ticket.assignee, ticket.work_status = "triage", None, "open"
    ticket.add_activity(body.reviewer, ticket.triage_state, body.notes or (ticket.assignee if final else None))
    db.commit()
    db.refresh(review)
    return review
