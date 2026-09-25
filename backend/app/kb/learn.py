"""Learning loop (spec section 8): finished work becomes retrievable knowledge, so the next
similar ticket finds a real precedent. A ticket enters the knowledge base only when the
specialist marks it done, with their own closing comment; never raw AI output."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KbDocument, Ticket
from app.pipeline import llm

DECISION_FIELDS = ("work_type", "service", "team", "urgency", "impact", "priority")


def final_decision(ticket: Ticket) -> dict:
    """The analyst's decision if they edited the proposal, else the latest AI proposal."""
    reviewed = next((r.final for r in ticket.reviews if r.final), None)
    if reviewed:
        return reviewed
    latest = ticket.triage_results[0]
    return {f: getattr(latest, f) for f in DECISION_FIELDS}


def learn_from_resolution(db: Session, ticket: Ticket) -> KbDocument:
    decision = final_decision(ticket)
    service = ticket.ai_service or decision["service"]
    ref_id = f"tkt-{ticket.number}"
    content = (
        f"Service: {service}. Past ticket #{ticket.number}: {ticket.summary}. {ticket.description} "
        f"Decision: {decision['work_type']}, urgency {decision['urgency']}, impact {decision['impact']}, "
        f"priority {decision['priority']}, resolution {ticket.resolution}. {ticket.resolution_comment}"
    )
    meta = {
        "service": service,
        "resolver": ticket.resolved_by,
        "note": ticket.resolution_comment,
        "resolution": ticket.resolution,
        "quality": "resolved",
        "ticket_number": ticket.number,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
    }
    doc = db.scalar(select(KbDocument).where(KbDocument.ref_id == ref_id))
    if doc is None:
        doc = KbDocument(kind="historical_ticket", ref_id=ref_id, title="", content="", meta={})
        db.add(doc)
    doc.title = f"{service}: #{ticket.number} {ticket.summary[:80]}"
    doc.content, doc.meta = content, meta
    vectors = llm.embed([content])
    doc.embedding = vectors[0] if vectors else None
    return doc
