from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Ticket, User
from app.pipeline import llm


def validate_model(model: str | None) -> str | None:
    """Reject models that are not offered in /api/llm/models."""
    if model is None or model == llm.HEURISTIC:
        return model
    if model not in llm.available_model_ids():
        raise HTTPException(status_code=400, detail=f"Model '{model}' is not available. See GET /api/llm/models.")
    return model


# ---------------------------------------------------------------- who may do what
# There is no login (the UI's "View as" switcher stands in for it), so every state-changing call
# says who is acting and the backend checks that person's role against the ticket.

def get_actor(db: Session, email: str | None) -> User:
    user = db.get(User, email) if email else None
    if user is None:
        raise HTTPException(status_code=400, detail=f"Unknown user '{email}': send the email of the person acting")
    return user


def in_needs_review(ticket: Ticket) -> bool:
    """Waiting for any analyst: not triaged, low confidence, rejected, or no department yet."""
    return ticket.work_status == "open" and (
        ticket.triage_state in ("new", "rejected") or ticket.route == "triage" or ticket.ai_team is None)


def can_manage(user: User, ticket: Ticket) -> bool:
    """Decide, dispatch, reassign, de-escalate. Admin: any ticket. Team Lead / Analyst: their
    department's tickets, plus the shared Needs-review pool."""
    if user.role == "admin":
        return True
    return user.role == "analyst" and (ticket.ai_team in (user.teams or []) or in_needs_review(ticket))


def require_manager(user: User, ticket: Ticket, action: str) -> None:
    if not can_manage(user, ticket):
        raise HTTPException(status_code=403,
                            detail=f"Only the {ticket.ai_team or 'owning'} Team Lead / Analyst or an admin can {action}")


def can_escalate(user: User, ticket: Ticket) -> bool:
    """The specialist working on it, the department's analyst, or an admin."""
    return can_manage(user, ticket) or user.email == ticket.assignee


def require_creator(user: User) -> None:
    if user.role not in ("analyst", "admin"):
        raise HTTPException(status_code=403, detail="Only a Team Lead / Analyst or an admin can create tickets")
