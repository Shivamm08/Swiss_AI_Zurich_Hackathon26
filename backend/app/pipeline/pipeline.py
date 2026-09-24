"""The triage pipeline: retrieve -> classify -> rules -> draft."""

import time

from sqlalchemy.orm import Session

from app.domain import normalize_level
from app.ingest import ticket_text
from app.models import Ticket, TriageResult
from app.pipeline import classify, draft, llm, retrieve, rules


def _changed_fields(ticket: Ticket, result: TriageResult) -> list[str]:
    intake = {
        "work_type": ticket.work_type,
        "service": ticket.affected_service,
        "urgency": normalize_level(ticket.urgency),
        "impact": normalize_level(ticket.impact),
        "priority": normalize_level(ticket.priority),
    }
    return [field for field, value in intake.items() if value != getattr(result, field)]


def run_triage(db: Session, ticket: Ticket, model: str | None = None) -> TriageResult:
    """`model` comes from the UI; None = configured default, "heuristic" = no LLM."""
    started = time.perf_counter()
    model = llm.resolve_model(model)

    evidence = retrieve.search(db, ticket_text(ticket), k=6)                   # 2. retrieve
    cls = classify.classify(ticket, evidence, model)                            # 3. LLM judgement
    playbook_doc = retrieve.get_document(db, cls.playbook_ref) if cls.playbook_ref else None

    result = TriageResult(                                                      # 4. deterministic rules
        ticket_id=ticket.id,
        work_type=cls.work_type,
        service=cls.service,
        team=rules.team(cls.service),
        assignee=rules.assignee(cls.service, playbook_doc),
        urgency=cls.urgency,
        impact=cls.impact,
        priority=rules.priority(cls.urgency, cls.impact),
        resolution=cls.resolution,
        resolution_comment=draft.draft_comment(ticket, cls, playbook_doc, model),  # 5. LLM draft
        confidence=cls.confidence,
        rationale=cls.rationale,
        evidence=[e.model_dump() for e in evidence],
        model=llm.model_name(model),
    )
    result.changed_fields = _changed_fields(ticket, result)
    result.latency_ms = int((time.perf_counter() - started) * 1000)

    db.add(result)
    ticket.triage_state = "proposed"
    db.commit()
    db.refresh(result)
    return result
