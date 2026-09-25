"""The triage pipeline (spec section 3):

retrieve -> extract (LLM, votes) -> rubric (code) -> confidence + route (code)
-> assignment (code) -> draft (LLM)

`triage_events` yields one event per stage so the UI can show a live walkthrough;
`run_triage` runs it to the end for batch use. Values staff confirmed when creating
the ticket (`ticket.manual`) are kept; the pipeline only fills the gaps.
"""

import time
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app import chat
from app.config import settings
from app.domain import normalize_level, priority_for
from app.ingest import ticket_text
from app.models import KbDocument, Ticket, TriageResult, User
from app.pipeline import assignment, classify, confidence, draft, llm, retrieve, rubric, rules
from app.schemas import Evidence, StaffCheck, TriageStreamEvent

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
    """Matched playbook entry (if it belongs to the chosen service), else the best approved past ticket."""
    if playbook_ref:
        doc = retrieve.get_document(db, playbook_ref)
        if doc and doc.meta.get("service") == service:
            return doc
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


def triage_events(db: Session, ticket: Ticket, model: str | None = None, sink: list | None = None) -> Iterator[TriageStreamEvent]:
    """Run the pipeline, yielding an event per stage. The final TriageResult is appended to `sink`."""
    started = time.perf_counter()
    now = datetime.now(timezone.utc)
    model = llm.resolve_model(model)
    manual = ticket.manual
    was_escalated = bool(ticket.escalated)

    def event(stage: str, status: str, message: str, data: dict[str, Any] | None = None) -> TriageStreamEvent:
        return TriageStreamEvent(stage=stage, status=status, message=message, data=data or {},  # type: ignore[arg-type]
                                 elapsed_ms=int((time.perf_counter() - started) * 1000))

    # 2. retrieve (embed once, reuse for search and confidence)
    yield event("retrieve", "started", "Searching service cards, the resolution playbook and approved past tickets")
    text = ticket_text(ticket)
    query_vector = retrieve.embed_query(text)
    evidence = retrieve.search(db, text, k=6, query_vector=query_vector)
    yield event("retrieve", "completed", f"Found {len(evidence)} relevant documents",
                {"evidence": [e.model_dump() for e in evidence], "hybrid": query_vector is not None})

    # 3. extract facts with votes
    votes = max(1, settings.llm_votes)
    yield event("extract", "started",
                f"Asking {model} for the observable facts: {votes} independent votes" if model else "No model selected: heuristic fallback")
    it = classify.classify_iter(ticket, evidence, model)
    while True:
        try:
            vote = next(it)
        except StopIteration as stop:
            cls = stop.value
            break
        yield event("vote", "completed" if vote["ok"] else "failed",
                    f"Vote {vote['index']} " + ("answered" if vote["ok"] else f"failed: {vote['error']}"), vote)
    ex = cls.extraction
    yield event("extract", "completed",
                "Heuristic fallback: " + (cls.fallback_reason or "") if cls.heuristic
                else f"Votes agree {round(cls.votes_score * 100)}%: {ex.work_type} on {ex.service}",
                {"extraction": ex.model_dump(), "vote_agreement": cls.vote_agreement, "votes_score": cls.votes_score,
                 "heuristic": cls.heuristic, "manual": sorted(k for k in manual if k in classify.MANUAL_EXTRACTION_FIELDS),
                 "staff_checks": cls.staff_checks})
    reference = _reference_doc(db, ex.playbook_ref, evidence, ex.service)

    # 4. rubric -> impact, urgency, priority, 0..1 score (staff-set urgency/impact win)
    opened_at = ticket.source_created_at or ticket.created_at or now
    rub = rubric.apply_rubric(ex.facts(), ex.service, ex.work_type, age_days=(now - opened_at).total_seconds() / 86400)
    staff_checks = list(cls.staff_checks)
    urgency, impact = manual.get("urgency", rub.urgency), manual.get("impact", rub.impact)
    priority, score, trace = rub.priority, rub.priority_score, list(rub.trace)
    staff_set = [k for k in ("impact", "urgency") if k in manual]
    if staff_set:
        priority = priority_for(urgency, impact)
        score = rubric.rescore(rub.priority, rub.priority_score, priority)
        replaced = ("Priority", *(k.capitalize() for k in staff_set))
        trace = [line for line in trace if not line.startswith(replaced)]
        trace += [f"{k.capitalize()} {manual[k]}: set by staff" for k in staff_set]
        for k in staff_set:  # the rules' own answer is the check on the staff value
            ruled = getattr(rub, k)
            if manual[k] != ruled:
                why = next((line for line in rub.trace if line.startswith(k.capitalize())), f"{k.capitalize()} {ruled}")
                staff_checks.append({"field": k, "staff": manual[k], "checked": ruled, "by": "rules", "note": why})
        trace.append(f"Priority {priority} = matrix[urgency {urgency}][impact {impact}]")
    yield event("rubric", "completed", f"Impact {impact} · Urgency {urgency} → Priority {priority}",
                {"facts": ex.facts().model_dump(), "impact": impact, "urgency": urgency, "priority": priority,
                 "priority_score": score, "trace": trace, "critical": rub.critical})

    # 6-7. confidence, route, escalation, SLA
    candidates = [reference.ref_id] if reference else [e.ref_id for e in evidence if e.kind != "service_card"][:1]
    similarity = retrieve.cosine_similarity(db, query_vector, candidates).get(candidates[0]) if candidates else None
    team = rules.team(ex.service)
    if manual.get("assignee"):  # the roster is the check on a staff-chosen specialist
        person = db.get(User, manual["assignee"])
        if person is None or person.role != "specialist" or team not in (person.teams or []):
            staff_checks.append({"field": "assignee", "staff": manual["assignee"], "checked": f"a {team} specialist",
                                 "by": "rules", "note": f"{team} owns {ex.service}; this person isn't one of its specialists"})
    flags = _flags(ticket, ex.service) + (["staff_disagreement"] if staff_checks else [])
    conf = confidence.score(
        cls.votes_score,
        confidence.retrieval_score(similarity, matched=reference is not None),
        flags,
        cls.heuristic,
    )
    conf.staff_checks = [StaffCheck(**c) for c in staff_checks]
    route = confidence.route_for(conf.overall)
    escalated = priority == "Highest" and rub.critical
    sla_due_at = confidence.sla_due(ticket.created_at or now, priority)
    yield event("confidence", "completed", f"Confidence {round(conf.overall * 100)}% → route: {route}",
                {"confidence": conf.model_dump(), "route": route, "escalated": escalated, "sla_due_at": sla_due_at.isoformat()})

    # assignment: expert for the export, a suggested specialist for the analyst (staff choice wins).
    # The AI never dispatches: an analyst approves every ticket before a specialist gets it.
    expert = rules.assignee(ex.service, reference)
    suggestion = assignment.suggest(db, team, ex.service, expert, ticket_id=ticket.id)
    if manual.get("assignee"):
        suggestion.recommended, suggestion.reason = manual["assignee"], "assignee set by staff"
    suggested = suggestion.recommended if (route != "triage" or manual.get("assignee")) else None
    waiting_for = f"{team} analyst" if route != "triage" else "Needs review (any analyst)"
    yield event("assign", "completed",
                f"Expert {expert or 'none'} · suggested specialist {suggested or 'none'} · waiting for the {waiting_for}",
                {"suggestion": suggestion.model_dump(), "suggested_assignee": suggested, "waiting_for": waiting_for})

    # 5. draft, in the voice of the agent who will close it (staff comment wins)
    yield event("draft", "started", "Writing the resolution comment from the closest past solution")
    comment = manual.get("resolution_comment") or draft.draft_comment(
        ticket, ex, reference, model, assignee=manual.get("assignee") or expert or suggestion.recommended)
    yield event("draft", "completed", "Resolution comment ready",
                {"comment": comment, "reference": reference.ref_id if reference else None})

    result = TriageResult(
        ticket_id=ticket.id,
        work_type=ex.work_type,
        service=ex.service,
        team=team,
        assignee=manual.get("assignee") or expert,
        urgency=urgency,
        impact=impact,
        priority=priority,
        resolution=ex.resolution,
        resolution_comment=comment,
        confidence=conf.overall,
        confidence_detail=conf.model_dump(),
        facts=ex.facts().model_dump(),
        priority_score=score,
        rubric_trace=trace,
        vote_agreement=cls.vote_agreement,
        route=route,
        escalated=escalated,
        sla_due_at=sla_due_at,
        assignee_suggestion=suggestion.model_dump(),
        playbook_ref=reference.ref_id if reference else None,
        rationale=ex.rationale,
        evidence=[e.model_dump() for e in evidence],
        model=llm.model_name(model),
    )
    result.changed_fields = _changed_fields(ticket, result)
    result.latency_ms = int((time.perf_counter() - started) * 1000)

    # Copy onto the ticket so the queue can filter/sort without joins. Work already dispatched
    # or under way keeps its assignee; otherwise the ticket waits for an analyst.
    ticket.triage_state = "proposed"
    if ticket.work_status == "open":
        ticket.assignee = None
    ticket.add_activity(chat.SYSTEM_SENDER, "triaged", f"{route} · {round(conf.overall * 100)}% · {llm.model_name(model)}")
    ticket.ai_service, ticket.ai_team, ticket.ai_priority = result.service, result.team, result.priority
    ticket.priority_score, ticket.confidence, ticket.route = result.priority_score, result.confidence, route
    ticket.escalated, ticket.sla_due_at = escalated, sla_due_at

    db.add(result)
    if escalated and not was_escalated:  # tell the owning team right away
        who = chat.names(db).get(suggested or "", "")
        chat.post(db, chat.team_channel(team), chat.SYSTEM_SENDER,
                  f"Escalation: #{ticket.number} \"{ticket.summary}\" is {priority} on {ex.service} (critical). "
                  f"Needs an analyst decision now{f'; suggested specialist {who}' if who else ''}. "
                  f"Response due within {confidence.SLA_HOURS[priority]:g} h.",
                  kind="escalation", ticket_id=ticket.id)
    db.commit()
    db.refresh(result)
    if sink is not None:
        sink.append(result)
    yield event("done", "completed", f"Proposal ready in {result.latency_ms / 1000:.1f}s", {"triage_result_id": str(result.id)})


def run_triage(db: Session, ticket: Ticket, model: str | None = None) -> TriageResult:
    """`model` comes from the UI; None = configured default, "heuristic" = no LLM."""
    sink: list[TriageResult] = []
    for _ in triage_events(db, ticket, model, sink):
        pass
    return sink[0]
