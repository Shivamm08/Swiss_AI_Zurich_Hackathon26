from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import chat
from app.api.deps import validate_model
from app.db import get_db
from app.domain import SERVICE_CATALOG, TEAMS
from app.ingest import ticket_text
from app.models import Message, Ticket, User
from app.pipeline import llm
from app.pipeline.assignment import open_clause, open_counts
from app.schemas import (
    ChannelOut,
    Department,
    DraftOut,
    DraftRequest,
    MemberBrief,
    MessageCreate,
    MessageOut,
    ServiceBrief,
)

router = APIRouter(tags=["messaging"])

DRAFT_PROMPT = """You write short internal messages for an asset manager's IT service desk.
Write 3-5 sentences, plain text, no subject line, no sign-off, first person as the sender.
Always include the ticket number, what is affected, the priority and the SLA deadline, and one
concrete ask. Purpose "escalate": ask the recipient to take ownership now. "handoff": hand the ticket
over with the context they need. "question": ask for the specific missing information."""


def _latest(db: Session, channel: str) -> Message | None:
    return db.scalar(select(Message).where(Message.channel == channel).order_by(Message.created_at.desc()).limit(1))


@router.get("/chat/channels", response_model=list[ChannelOut])
def list_channels(as_user: str = Query(..., description="Email of the person viewing"), db: Session = Depends(get_db)) -> list[ChannelOut]:
    lookup = chat.names(db)
    counts = dict(db.execute(select(Message.channel, func.count()).group_by(Message.channel)).all())
    channels: list[ChannelOut] = []
    for team in TEAMS:
        cid = chat.team_channel(team)
        last = _latest(db, cid)
        services = [s for s, (t, _) in SERVICE_CATALOG.items() if t == team]
        channels.append(ChannelOut(
            id=cid, kind="team", title=team, subtitle=", ".join(services),
            members=chat.channel_members(db, cid), message_count=counts.get(cid, 0),
            last_message=chat.to_out(db, last, lookup) if last else None,
        ))
    me = as_user.lower()
    for cid in (c for c in counts if c.startswith("dm:") and me in c[3:].split("|")):
        other = next((m for m in cid[3:].split("|") if m != me), me)
        last = _latest(db, cid)
        channels.append(ChannelOut(
            id=cid, kind="dm", title=lookup.get(other, other), subtitle="Direct message",
            members=cid[3:].split("|"), message_count=counts.get(cid, 0),
            last_message=chat.to_out(db, last, lookup) if last else None,
        ))
    return channels


@router.get("/chat/messages", response_model=list[MessageOut])
def list_messages(channel: str, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)) -> list[MessageOut]:
    try:
        channel = chat.normalize_channel(channel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rows = db.scalars(select(Message).where(Message.channel == channel).order_by(Message.created_at.desc()).limit(limit)).all()
    lookup = chat.names(db)
    return [chat.to_out(db, m, lookup) for m in reversed(rows)]


@router.post("/chat/messages", response_model=MessageOut, status_code=201)
def send_message(body: MessageCreate, db: Session = Depends(get_db)) -> MessageOut:
    if body.ticket_id and db.get(Ticket, body.ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        message = chat.post(db, body.channel, body.sender, body.body.strip(), body.kind, body.ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(message)
    return chat.to_out(db, message)


@router.post("/chat/draft", response_model=DraftOut)
def draft_message(body: DraftRequest, db: Session = Depends(get_db)) -> DraftOut:
    """AI-drafted escalation / hand-off / question about a ticket, addressed to a person or a team."""
    ticket = db.get(Ticket, body.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    lookup = chat.names(db)
    if body.to.startswith("team:"):
        channel, label = chat.team_channel(body.to[5:]), f"{body.to[5:]} team"
    else:
        channel, label = chat.dm_channel(body.sender, body.to), lookup.get(body.to, body.to)
    latest = ticket.triage_results[0] if ticket.triage_results else None
    context = ticket_text(ticket)
    if latest:
        context += (f"\nTriage: {latest.work_type} on {latest.service} ({latest.team}), priority {latest.priority}, "
                    f"SLA due {ticket.sla_due_at:%Y-%m-%d %H:%M} UTC, confidence {round(latest.confidence * 100)}%. "
                    f"Proposed resolution: {latest.resolution_comment}")
    model = llm.resolve_model(validate_model(body.model))
    user = f"SENDER: {lookup.get(body.sender, body.sender)}\nRECIPIENT: {label}\nPURPOSE: {body.purpose}\nTICKET #{ticket.number}\n{context}"
    try:
        text = llm.complete(DRAFT_PROMPT, user, model)
    except Exception:
        text = None
    if not text:
        priority = latest.priority if latest else ticket.priority or "unknown"
        asks = {"escalate": "Can you take ownership now?", "handoff": "Handing this over to you with the context above.",
                "question": "Could you share the missing details so we can proceed?"}
        text = (f"Ticket #{ticket.number} \"{ticket.summary}\" is {priority} priority"
                f"{f' on {latest.service}' if latest else ''}. {asks[body.purpose]}")
    return DraftOut(channel=channel, recipient_label=label, body=text.strip(),
                    kind="escalation" if body.purpose == "escalate" else "handoff" if body.purpose == "handoff" else "message",
                    model=llm.model_name(model))


@router.get("/directory", response_model=list[Department])
def get_directory(db: Session = Depends(get_db)) -> list[Department]:
    users = db.scalars(select(User).where(User.role != "admin")).all()
    counts = open_counts(db)
    active = db.scalars(select(Ticket).where(open_clause())).all()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    weekly = dict(db.execute(select(Message.channel, func.count()).where(Message.created_at >= week_ago)
                             .group_by(Message.channel)).all())
    out = []
    for team in TEAMS:
        members = [MemberBrief(email=u.email, name=u.name, role=u.role, open=counts[u.email], capacity=u.capacity)  # type: ignore[arg-type]
                   for u in users if team in (u.teams or [])]
        members.sort(key=lambda m: (m.role != "lead", m.name))
        team_tickets = [t for t in active if t.ai_team == team]
        out.append(Department(
            team=team, channel=chat.team_channel(team),
            services=[ServiceBrief(name=s, criticality=c) for s, (t, c) in SERVICE_CATALOG.items() if t == team],
            lead=next((m for m in members if m.role == "lead"), None), members=members,
            open_tickets=len(team_tickets), escalations=sum(1 for t in team_tickets if t.escalated),
            messages_7d=weekly.get(chat.team_channel(team), 0),
        ))
    return out
