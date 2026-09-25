"""Database tables. After changing this file, create a migration:

    make migration m="describe the change"
"""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Identity, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db import Base


class Ticket(Base):
    """An incoming ticket exactly as it arrived (intake values may be wrong)."""

    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    number: Mapped[int] = mapped_column(Integer, Identity(), unique=True)
    source: Mapped[str] = mapped_column(String(20), index=True)  # challenge | training | manual | email

    work_type: Mapped[str | None] = mapped_column(String(40))
    request_type: Mapped[str | None] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    affected_service: Mapped[str | None] = mapped_column(String(80))
    business_entity: Mapped[str | None] = mapped_column(String(40))
    reporter: Mapped[str | None] = mapped_column(String(120))
    urgency: Mapped[str | None] = mapped_column(String(10))
    impact: Mapped[str | None] = mapped_column(String(10))
    priority: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str | None] = mapped_column(String(20))
    linked_issues: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    comments: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))  # original record, used by export

    # new | proposed | approved | edited | rejected (denormalised for queue filtering)
    triage_state: Mapped[str] = mapped_column(String(20), default="new", server_default="new", index=True)

    # Working assignment (workload-aware) + fields copied from the latest proposal for fast queue queries.
    assignee: Mapped[str | None] = mapped_column(String(120), index=True)
    ai_service: Mapped[str | None] = mapped_column(String(80))
    ai_team: Mapped[str | None] = mapped_column(String(80), index=True)
    ai_priority: Mapped[str | None] = mapped_column(String(10))
    priority_score: Mapped[float | None] = mapped_column(Float, index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    route: Mapped[str | None] = mapped_column(String(10), index=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def manual(self) -> dict[str, Any]:
        """Values confirmed by staff in the New-ticket form (stored in raw, no extra column)."""
        return dict((self.raw or {}).get("manual") or {})

    @property
    def manual_fields(self) -> list[str]:
        return list(self.manual)

    triage_results: Mapped[list["TriageResult"]] = relationship(
        back_populates="ticket", order_by="TriageResult.created_at.desc()", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="ticket", order_by="Review.created_at.desc()", cascade="all, delete-orphan"
    )


class TriageResult(Base):
    """One AI proposal for a ticket. Re-running triage adds a new row."""

    __tablename__ = "triage_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)

    work_type: Mapped[str] = mapped_column(String(40))
    service: Mapped[str] = mapped_column(String(80))
    team: Mapped[str] = mapped_column(String(80))
    assignee: Mapped[str | None] = mapped_column(String(120))
    urgency: Mapped[str] = mapped_column(String(10))
    impact: Mapped[str] = mapped_column(String(10))
    priority: Mapped[str] = mapped_column(String(10))
    resolution: Mapped[str] = mapped_column(String(30))
    resolution_comment: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text, default="", server_default="")
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    changed_fields: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    model: Mapped[str] = mapped_column(String(80))
    latency_ms: Mapped[int] = mapped_column(Integer)

    # Spec additions: facts -> rubric, confidence breakdown, routing, assignment.
    facts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    priority_score: Mapped[float | None] = mapped_column(Float)
    rubric_trace: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    vote_agreement: Mapped[dict[str, float]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    confidence_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    route: Mapped[str | None] = mapped_column(String(10))
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignee_suggestion: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    playbook_ref: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped[Ticket] = relationship(back_populates="triage_results")


class Review(Base):
    """An analyst decision on a proposal: approve, edit or reject."""

    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    triage_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("triage_results.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(10))  # approve | edit | reject
    final: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    overridden_fields: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    reviewer: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    review_seconds: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped[Ticket] = relationship(back_populates="reviews")


class KbDocument(Base):
    """Retrieval corpus: service cards, playbook entries, (later) historical tickets."""

    __tablename__ = "kb_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    kind: Mapped[str] = mapped_column(String(30), index=True)  # service_card | playbook | historical_ticket
    ref_id: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dim), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base):
    """Roster: people, their teams, role and capacity (generated, see kb/roster.yaml)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(10), default="analyst", server_default="analyst")  # analyst | lead | admin
    teams: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    capacity: Mapped[int] = mapped_column(Integer, default=8, server_default="8")


class Message(Base):
    """Team channels and direct messages (spec: People & teams, escalations).

    channel: "team:<Team name>" for a department channel, "dm:<email_a>|<email_b>" (sorted) for a
    direct conversation. kind: message | system | escalation | handoff.
    """

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    channel: Mapped[str] = mapped_column(String(300), index=True)
    sender: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20), default="message", server_default="message")
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
