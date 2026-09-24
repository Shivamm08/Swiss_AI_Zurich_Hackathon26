"""Step 3: the LLM makes the judgement calls.

Returns work type, true service, urgency, impact, resolution status and the
best matching playbook entry. Team, priority and assignee are NOT decided here;
rules.py derives them so they can never be inconsistent.
"""

from pydantic import BaseModel

from app.domain import (
    IMPACT_LABELS,
    SERVICE_CATALOG,
    URGENCY_LABELS,
    Level,
    Resolution,
    ServiceName,
    WorkType,
    as_service,
    normalize_level,
)
from app.ingest import ticket_text
from app.models import Ticket
from app.pipeline import llm
from app.schemas import Evidence


class Classification(BaseModel):
    work_type: WorkType
    service: ServiceName
    urgency: Level
    impact: Level
    resolution: Resolution
    playbook_ref: str | None
    confidence: float
    rationale: str


def _catalogue() -> str:
    return "\n".join(f"- {name} (team: {team}, {crit})" for name, (team, crit) in SERVICE_CATALOG.items())


SYSTEM_PROMPT = f"""You are an experienced L2 service desk agent at a pan-European asset manager.
Triage the ticket. Rules:
- The intake service and the title can be wrong on purpose. Decide from the content.
- "Emailed Support Tickets" is a generic intake bucket; only choose it if no real service applies.
- Request type is a strong hint (e.g. "Misclassified Incident Title" means the title is misleading).
- Incident = something is broken or degraded. Service Request = someone asks for something (access, licence, mailbox).
- Urgency levels: {URGENCY_LABELS}. Impact levels: {IMPACT_LABELS}.
  A failure on a Critical service justifies higher urgency/impact than the same failure on a Non-Critical one.
- Resolution: done = a concrete fix/fulfilment applies; clarification = too vague to act on;
  cannot reproduce = symptom not confirmed; cancelled = duplicate, withdrawn or no action needed.
- playbook_ref: the ref_id of the retrieved playbook entry that matches this problem, or null.
- confidence: 0..1.

Service catalogue:
{_catalogue()}
"""


def _prompt(ticket: Ticket, evidence: list[Evidence]) -> str:
    refs = "\n\n".join(f"[{e.ref_id}] ({e.kind}) {e.title}\n{e.snippet}" for e in evidence)
    return f"TICKET\n{ticket_text(ticket)}\n\nRETRIEVED KNOWLEDGE\n{refs or '(none)'}"


def _heuristic(ticket: Ticket, evidence: list[Evidence]) -> Classification:
    """Fallback when Azure OpenAI is not configured. Deliberately simple."""
    top_card = next((e for e in evidence if e.kind == "service_card"), None)
    service = as_service(ticket.affected_service) or (as_service(top_card.title) if top_card else None)
    service = service or "Emailed Support Tickets"
    playbook = next(
        (e for e in evidence if e.kind == "playbook" and e.title.startswith(service)), None
    )
    unclear = (ticket.request_type or "").lower().startswith("nonsense")
    return Classification(
        work_type="Service Request" if ticket.work_type == "Service Request" else "Incident",
        service=service,
        urgency=normalize_level(ticket.urgency) or "Medium",
        impact=normalize_level(ticket.impact) or "Medium",
        resolution="clarification" if unclear else "done",
        playbook_ref=playbook.ref_id if playbook else None,
        confidence=0.3,
        rationale="Heuristic fallback (no LLM model selected): kept intake values.",
    )


def classify(ticket: Ticket, evidence: list[Evidence], model: str | None) -> Classification:
    result = llm.parse(SYSTEM_PROMPT, _prompt(ticket, evidence), Classification, model)
    if result is None:
        return _heuristic(ticket, evidence)
    result.confidence = min(max(result.confidence, 0.0), 1.0)
    if result.playbook_ref and result.playbook_ref not in {e.ref_id for e in evidence}:
        result.playbook_ref = None  # never trust a reference that was not retrieved
    return result
