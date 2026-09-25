from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.domain import TEAMS
from app.models import Ticket, User
from app.pipeline.assignment import open_counts, team_members
from app.schemas import TicketOut, UserOut, Workload, WorkloadMember

router = APIRouter(tags=["people"])


@router.get("/users", response_model=list[UserOut])
def list_users(team: str | None = None, db: Session = Depends(get_db)) -> list[User]:
    users = db.scalars(select(User).order_by(User.role.desc(), User.name)).all()
    return [u for u in users if team is None or team in (u.teams or [])]


@router.get("/workload", response_model=Workload)
def get_workload(team: str = Query(..., description="Team name, e.g. 'Client Services'"), db: Session = Depends(get_db)) -> Workload:
    if team not in TEAMS:
        raise HTTPException(status_code=404, detail=f"Unknown team '{team}'")
    members = team_members(db, team)
    counts = open_counts(db)
    active = db.scalars(select(Ticket).where(Ticket.ai_team == team, Ticket.work_status != "done")).all()
    team_open = sum(counts[m.email] for m in members)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    resolved = db.scalars(select(Ticket.resolved_by).where(Ticket.work_status == "done", Ticket.resolved_at >= week_ago)).all()

    rows = []
    for m in members:
        mine = [t for t in active if t.assignee == m.email and t.work_status != "open"]
        rows.append(WorkloadMember(
            email=m.email, name=m.name, role=m.role, open=counts[m.email],
            capacity=m.capacity or settings.default_capacity,
            share=round(counts[m.email] / team_open, 3) if team_open else 0.0,
            high_open=sum(1 for t in mine if t.ai_priority in ("High", "Highest")),
            oldest_open_at=min((t.created_at for t in mine), default=None),
            resolved_7d=resolved.count(m.email),
        ))
    rows.sort(key=lambda r: r.open, reverse=True)
    escalations = sorted((t for t in active if t.escalated), key=lambda t: -(t.priority_score or 0))
    return Workload(team=team, open_total=team_open, members=rows,
                    escalations=[TicketOut.model_validate(t) for t in escalations])
