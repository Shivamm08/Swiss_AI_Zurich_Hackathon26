"""Workload-aware assignment (spec section 7).

Two assignees are kept apart on purpose:
- expert:      resolver of the matched playbook entry. This is what the challenge
               scores, so the proposal/export uses it.
- recommended: best specialist in the team after balancing expertise and availability;
               the analyst dispatches the ticket to them (or picks someone else).
"""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Ticket, User
from app.schemas import AssigneeCandidate, AssigneeSuggestion

ACTIVE_WORK = ("assigned", "in_progress", "waiting")  # with a specialist, not done yet


def open_clause():
    """SQL condition for 'a specialist is working on it' (counts towards their workload)."""
    return Ticket.work_status.in_(ACTIVE_WORK)


def is_open(ticket: Ticket) -> bool:
    return ticket.work_status in ACTIVE_WORK


W_EXPERTISE, W_AVAILABILITY = 0.6, 0.4
EXPERTISE_SATURATION = 5  # closed tickets on a service for full learned expertise


def open_counts(db: Session, exclude_ticket=None) -> Counter:
    stmt = select(Ticket.assignee).where(Ticket.assignee.is_not(None), open_clause())
    if exclude_ticket is not None:
        stmt = stmt.where(Ticket.id != exclude_ticket)
    return Counter(db.scalars(stmt))


def resolved_on_service(db: Session, service: str) -> Counter:
    """How many tickets on this service each specialist closed (learned expertise)."""
    return Counter(db.scalars(select(Ticket.resolved_by).where(
        Ticket.work_status == "done", Ticket.ai_service == service, Ticket.resolved_by.is_not(None))))


def team_members(db: Session, team: str) -> list[User]:
    """The specialists of a team: the people who can be assigned work."""
    return [u for u in db.scalars(select(User).where(User.role == "specialist")) if team in (u.teams or [])]


def suggest(db: Session, team: str, service: str, expert: str | None, ticket_id=None) -> AssigneeSuggestion:
    members = team_members(db, team)
    if not members:
        return AssigneeSuggestion(expert=expert, recommended=expert, reason="no roster for this team", candidates=[])

    counts = open_counts(db, exclude_ticket=ticket_id)
    team_open = sum(counts[m.email] for m in members)
    learned = resolved_on_service(db, service)

    candidates: list[AssigneeCandidate] = []
    for m in members:
        capacity = m.capacity or settings.default_capacity
        expertise = min(1.0, (1.0 if m.email == expert else 0.0) + 0.5 * min(1.0, learned[m.email] / EXPERTISE_SATURATION))
        availability = max(0.0, 1 - counts[m.email] / capacity)
        candidates.append(AssigneeCandidate(
            user=m.email, name=m.name, open=counts[m.email], capacity=capacity, expertise=round(expertise, 3),
            score=round(W_EXPERTISE * expertise + W_AVAILABILITY * availability, 3),
        ))
    candidates.sort(key=lambda c: c.score, reverse=True)

    def blocked(c: AssigneeCandidate) -> bool:
        # The share rule only applies once the team has real volume (2+ open tickets per member);
        # below that, small teams would be blocked from their natural fair share.
        over_share = team_open >= 2 * len(members) and c.open / max(team_open, 1) >= settings.max_share
        return c.open >= c.capacity or over_share

    eligible = [c for c in candidates if not blocked(c)] or candidates
    recommended = eligible[0].user
    expert_c = next((c for c in candidates if c.user == expert), None)
    if expert is None:
        reason = "no matching past resolution: balanced by workload within the team"
    elif recommended == expert:
        reason = "expert on this problem and has capacity"
    elif expert_c and expert_c.open >= expert_c.capacity:
        reason = f"expert over capacity ({expert_c.open}/{expert_c.capacity}): next best team member"
    elif expert_c and blocked(expert_c):
        reason = f"expert already holds {expert_c.open} of the team's {team_open} open tickets: next best team member"
    else:
        reason = "expert is not in the roster for this team: best available team member"
    return AssigneeSuggestion(expert=expert, recommended=recommended, reason=reason, candidates=candidates)
