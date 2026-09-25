"""The triage pipeline (spec section 3):

retrieve -> extract (LLM, votes) -> rubric (code) -> confidence + route (code)
-> assignment (code) -> draft (LLM)
"""

import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain import normalize_level
from app.ingest import ticket_text
from app.models import KbDocument, Ticket, TriageResult
from app.pipeline import assignment, classify, confidence, draft, llm, retrieve, rubric, rules
from app.schemas import Evidence

GENERIC_SERVICE = "Emailed Support Tickets"


def _changed_fields(ticket: Ticket, result: TriageResult) -> list[str]:
    intake = {
        "work_type": ticket.work_type,
        "service": ticket.affected_service,
        "urgency": normalize_level(ticket.urgency),
        "impact": normalize_level(ticket.impact),
        "priority": normalize_level(ticket.priority),
    }
    return [f for f, value in intake.items() if value is not None and value != getattr(result, f)]


def _reference_doc(db: Session, playbook_ref: str | None, evidence: list[Evidence], service: str) -> KbDocument | None:
    """Matched playbook entry, else the best approved past ticket on the same service."""
    if playbook_ref:
        return retrieve.get_document(db, playbook_ref)
    learned = next((e for e in evidence if e.kind == "historical_ticket" and e.title.startswith(service)), None)
    return retrieve.get_document(db, learned.ref_id) if learned else None


def _flags(ticket: Ticket, service: str) -> list[str]:
    flags = []
    if service == GENERIC_SERVICE:
        flags.append("generic_service")
    request_type = (ticket.request_type or "").lower()
    if request_type.startswith("nonsense") or "unclear" in request_type:
        flags.append("unclear_input")
    return flags


def run_triage(db: Session, ticket: Ticket, model: str | None = None) -> TriageResult:
    """`model` comes from the UI; None = configured default, "heuristic" = no LLM."""
    started = time.perf_counter()
    now = datetime.now(timezone.utc)
    model = llm.resolve_model(model)

    # 2. retrieve (embed once, reuse for search and confidence)
    text = ticket_text(ticket)
    query_vector = retrieve.embed_query(text)
    evidence = retrieve.search(db, text, k=6, query_vector=query_vector)

    # 3. extract facts with votes
    cls = classify.classify(ticket, evidence, model)
    ex = cls.extraction
    reference = _reference_doc(db, ex.playbook_ref, evidence, ex.service)

    # 4. rubric -> impact, urgency, priority, 0..1 score
    opened_at = ticket.source_created_at or ticket.created_at or now
    rub = rubric.apply_rubric(ex.facts(), ex.service, ex.work_type, age_days=(now - opened_at).total_seconds() / 86400)

    # 6-7. confidence, route, escalation, SLA
    candidates = [reference.ref_id] if reference else [e.ref_id for e in evidence if e.kind != "service_card"][:1]
    similarity = retrieve.cosine_similarity(db, query_vector, candidates).get(candidates[0]) if candidates else None
    conf = confidence.score(
        cls.votes_score,
        confidence.retrieval_score(similarity, matched=reference is not None),
        _flags(ticket, ex.service),
        cls.heuristic,
    )
    route = confidence.route_for(conf.overall)

    # assignment: expert for the export, recommendation for the working queue
    team = rules.team(ex.service)
    expert = rules.assignee(ex.service, reference)
    suggestion = assignment.suggest(db, team, ex.service, expert, ticket_id=ticket.id)

    result = TriageResult(
        ticket_id=ticket.id,
        work_type=ex.work_type,
        service=ex.service,
        team=team,
        assignee=expert,
        urgency=rub.urgency,
        impact=rub.impact,
        priority=rub.priority,
        resolution=ex.resolution,
        # 5. draft, in the voice of the agent who will close it
        resolution_comment=draft.draft_comment(ticket, ex, reference, model, assignee=expert or suggestion.recommended),
        confidence=conf.overall,
        confidence_detail=conf.model_dump(),
        facts=ex.facts().model_dump(),
        priority_score=rub.priority_score,
        rubric_trace=rub.trace,
        vote_agreement=cls.vote_agreement,
        route=route,
        escalated=rub.priority == "Highest" and rub.critical,
        sla_due_at=confidence.sla_due(ticket.created_at or now, rub.priority),
        assignee_suggestion=suggestion.model_dump(),
        playbook_ref=reference.ref_id if reference else None,
        rationale=ex.rationale,
        evidence=[e.model_dump() for e in evidence],
        model=llm.model_name(model),
    )
    result.changed_fields = _changed_fields(ticket, result)
    result.latency_ms = int((time.perf_counter() - started) * 1000)

    # Copy onto the ticket so the queue can filter/sort without joins.
    ticket.triage_state = "proposed"
    ticket.assignee = suggestion.recommended if route != "triage" else None
    ticket.ai_service, ticket.ai_team, ticket.ai_priority = result.service, result.team, result.priority
    ticket.priority_score, ticket.confidence, ticket.route = result.priority_score, result.confidence, route
    ticket.escalated, ticket.sla_due_at = result.escalated, result.sla_due_at

    db.add(result)
    db.commit()
    db.refresh(result)
    return result
