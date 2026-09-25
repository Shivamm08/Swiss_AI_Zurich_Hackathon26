"""Messaging helpers: channel ids, posting, and turning rows into API objects.

Channels are plain strings, so there is no channel table:
- "team:<Team name>"          one per department
- "dm:<email_a>|<email_b>"     a direct conversation (emails sorted)
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import TEAMS
from app.models import Message, Ticket, User
from app.schemas import MessageOut

SYSTEM_SENDER = "triage-copilot"
SYSTEM_NAME = "Triage Copilot"


def team_channel(team: str) -> str:
    return f"team:{team}"


def dm_channel(a: str, b: str) -> str:
    x, y = sorted((a.strip().lower(), b.strip().lower()))
    return f"dm:{x}|{y}"


def normalize_channel(channel: str) -> str:
    """Accept dm channels in any member order; validate team names."""
    if channel.startswith("dm:"):
        members = channel[3:].split("|")
        if len(members) != 2 or not all("@" in m for m in members):
            raise ValueError("A direct channel looks like dm:<email>|<email>")
        return dm_channel(*members)
    if channel.startswith("team:") and channel[5:] in TEAMS:
        return channel
    raise ValueError(f"Unknown channel '{channel}'")


def channel_members(db: Session, channel: str) -> list[str]:
    if channel.startswith("dm:"):
        return channel[3:].split("|")
    team = channel[5:]
    return [u.email for u in db.scalars(select(User)) if team in (u.teams or [])]


def names(db: Session) -> dict[str, str]:
    lookup = {u.email: u.name for u in db.scalars(select(User))}
    lookup[SYSTEM_SENDER] = SYSTEM_NAME
    return lookup


def to_out(db: Session, message: Message, lookup: dict[str, str] | None = None) -> MessageOut:
    lookup = lookup or names(db)
    ticket = db.get(Ticket, message.ticket_id) if message.ticket_id else None
    return MessageOut(
        id=message.id,
        channel=message.channel,
        sender=message.sender,
        sender_name=lookup.get(message.sender, message.sender.split("@")[0]),
        body=message.body,
        kind=message.kind,  # type: ignore[arg-type]
        ticket_id=message.ticket_id,
        ticket_number=ticket.number if ticket else None,
        ticket_summary=ticket.summary if ticket else None,
        created_at=message.created_at,
    )


def post(db: Session, channel: str, sender: str, body: str, kind: str = "message",
         ticket_id: uuid.UUID | None = None) -> Message:
    channel = normalize_channel(channel)
    message = Message(channel=channel, sender=sender, body=body, kind=kind, ticket_id=ticket_id)
    db.add(message)
    if kind == "escalation" and ticket_id and (ticket := db.get(Ticket, ticket_id)):
        ticket.escalated = True
        target = channel[5:] if channel.startswith("team:") else next((m for m in channel[3:].split("|") if m != sender), None)
        ticket.add_activity(sender, "escalated", f"to {target}")
    return message
