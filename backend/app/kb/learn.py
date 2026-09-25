"""Learning loop (spec section 8): approved/edited decisions become retrievable
knowledge, so the next similar ticket finds a human-approved precedent.
Only human-approved results enter the knowledge base, never raw AI output."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KbDocument, Ticket
from app.pipeline import llm


def learn_from_review(db: Session, ticket: Ticket, final: dict, quality: str, reviewer: str) -> KbDocument:
    ref_id = f"tkt-{ticket.number}"
    resolver = ticket.assignee or final.get("assignee")
    content = (
        f"Service: {final['service']}. Past ticket #{ticket.number}: {ticket.summary}. {ticket.description} "
        f"Decision: {final['work_type']}, urgency {final['urgency']}, impact {final['impact']}, "
        f"priority {final['priority']}, resolution {final['resolution']}. {final['resolution_comment']}"
    )
    meta = {
        "service": final["service"],
        "resolver": resolver,
        "note": final["resolution_comment"],
        "quality": quality,
        "reviewer": reviewer,
        "ticket_number": ticket.number,
    }
    doc = db.scalar(select(KbDocument).where(KbDocument.ref_id == ref_id))
    if doc is None:
        doc = KbDocument(kind="historical_ticket", ref_id=ref_id, title="", content="", meta={})
        db.add(doc)
    doc.title = f"{final['service']}: #{ticket.number} {ticket.summary[:80]}"
    doc.content, doc.meta = content, meta
    vectors = llm.embed([content])
    doc.embedding = vectors[0] if vectors else None
    return doc
