"""Step 3: the LLM reads the ticket and reports what it observes.

It returns work type, the true service, observable FACTS (scope, outage,
workaround, regulatory, deadline), resolution status and the matching playbook
entry. It never names an Impact/Urgency/Priority: rubric.py decides those from
the facts. The extraction runs several times ("votes"); each field takes the
majority and the agreement rate becomes part of the confidence score.

Prompt design follows the lessons from the feature/apertus-triage branch:
enums/booleans only, and an ordered procedure with worked examples.
"""

import logging
from collections import Counter
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.config import settings
from app.domain import SERVICE_CATALOG, Resolution, ServiceName, WorkType, as_service
from app.ingest import ticket_text
from app.models import Ticket
from app.pipeline import llm
from app.schemas import Deadline, Evidence, Facts, Outage, Scope, Workaround

log = logging.getLogger(__name__)


class Extraction(BaseModel):
    work_type: WorkType
    service: ServiceName
    scope: Scope
    outage_extent: Outage
    workaround: Workaround
    regulatory_or_security: bool
    deadline_pressure: Deadline
    resolution: Resolution
    playbook_ref: str | None = Field(description="ref_id of the matching retrieved playbook entry, or null")
    rationale: str = Field(description="At most two short sentences")

    def facts(self) -> Facts:
        return Facts(
            scope=self.scope,
            outage_extent=self.outage_extent,
            workaround=self.workaround,
            regulatory_or_security=self.regulatory_or_security,
            deadline_pressure=self.deadline_pressure,
        )


# Voted fields and their weight in the vote score (service drives team, impact and assignee).
VOTE_WEIGHTS = {
    "work_type": 1.0,
    "service": 2.0,
    "scope": 1.0,
    "outage_extent": 1.0,
    "workaround": 1.0,
    "regulatory_or_security": 1.0,
    "deadline_pressure": 1.0,
    "resolution": 1.0,
    "playbook_ref": 1.0,
}


@dataclass
class Classification:
    extraction: Extraction
    vote_agreement: dict[str, float] = field(default_factory=dict)
    votes_score: float = 0.0
    heuristic: bool = False
    fallback_reason: str | None = None


def _catalogue() -> str:
    return "\n".join(f"- {name} (team: {team}, {crit})" for name, (team, crit) in SERVICE_CATALOG.items())


SYSTEM_PROMPT = f"""You are an experienced L2 IT service desk agent at a pan-European asset manager.
You read one Jira ticket and report the observable facts needed to triage it. Work through the steps in order.
Report only what the ticket says. Do not inflate severity. Never decide a priority yourself.

STEP 1 - work_type. Is something broken, or is someone asking for something?
  'Incident': an IT service is interrupted, degraded, erroring, delayed or behaving unexpectedly. Monitoring alerts,
  third-party warnings about a service and reported disruptions are Incidents.
  'Service Request': someone asks for something to be provided or withdrawn (licence, account, access, mailbox,
  provisioning, information). Nothing is broken.
  Judge from the description body; titles are misleading on purpose. The Request type field is a strong hint
  (e.g. "Misclassified Incident Title" means the title lies).

STEP 2 - service. Which service is actually affected? The intake service is often a guess; decide from the content
  and the retrieved service cards (respect their "not this" boundaries). "Emailed Support Tickets" is a generic
  intake bucket: choose it only if no real service applies.

STEP 3 - outage_extent. Follows from Step 1.
  Service Request -> 'none'. Incident -> never 'none':
  'full_unavailability' only if the service is completely unusable or fully down;
  'partial_degradation' for everything else (alerts, errors, delays, rejections, degraded performance).

STEP 4 - workaround. Service Request -> 'not_applicable'. Incident: 'easy' if a simple alternative is mentioned,
  'difficult' if the alternative is manual or slow, 'none' if the text gives no way around the fault.
  Do not invent a workaround.

STEP 5 - scope. The narrowest the text supports: 'individual' one person; 'team' one team or desk;
  'one_entity' one country/business entity, or a shared platform whose failure is not limited to named users;
  'multi_entity' more than one entity; 'external_counterparty' external clients, brokers, custodians or regulators
  are affected (including third-party warnings about client-facing output).

STEP 6 - regulatory_or_security: true ONLY for an actual regulatory breach, missed regulatory filing or security
  compromise, not merely because a regulated system is involved.

STEP 7 - deadline_pressure: 'hard' if a dated cutoff will be missed (NAV cutoff, settlement date, filing deadline,
  "today"); 'soft' if time matters without a stated cutoff; otherwise 'none'.

STEP 8 - resolution: 'done' if a concrete fix or fulfilment applies (usually when a playbook entry matches or the
  request is standard); 'clarification' if the ticket is too vague to act on; 'cannot reproduce' if the symptom is not
  confirmed; 'cancelled' if duplicate, withdrawn or no action is needed.

STEP 9 - playbook_ref: the ref_id of the RETRIEVED playbook entry describing the same problem, or null.

Worked examples:
  "Automated alert: job X failed with repeated execution errors, please confirm impact" -> Incident,
    partial_degradation, workaround none, scope one_entity, deadline none.
  "New user requires a licence for X" -> Service Request, outage none, workaround not_applicable, scope individual.
  "A custodian/vendor warns that feed X is delayed" -> Incident, partial_degradation, scope external_counterparty.
  "Cash not there pls fix asap" (no detail) -> Incident, partial_degradation, resolution clarification.

Service catalogue:
{_catalogue()}
"""


# Fields staff can confirm when creating a ticket; the AI must keep them.
MANUAL_EXTRACTION_FIELDS = ("work_type", "service", "resolution")


def _prompt(ticket: Ticket, evidence: list[Evidence]) -> str:
    refs = "\n\n".join(f"[{e.ref_id}] ({e.kind}) {e.title}\n{e.snippet}" for e in evidence)
    confirmed = {k: v for k, v in ticket.manual.items() if k in MANUAL_EXTRACTION_FIELDS}
    staff = (
        "\n\nCONFIRMED BY STAFF (keep these values exactly):\n" + "\n".join(f"- {k}: {v}" for k, v in confirmed.items())
        if confirmed else ""
    )
    return f"TICKET\n{ticket_text(ticket)}{staff}\n\nRETRIEVED KNOWLEDGE\n{refs or '(none)'}"


def _apply_manual(ticket: Ticket, cls: Classification) -> Classification:
    """Staff-confirmed values win over the model and count as certain in the vote score."""
    confirmed = {k: v for k, v in ticket.manual.items() if k in MANUAL_EXTRACTION_FIELDS}
    if not confirmed:
        return cls
    cls.extraction = cls.extraction.model_copy(update=confirmed)
    if not cls.heuristic:
        cls.vote_agreement.update({k: 1.0 for k in confirmed})
        total = sum(VOTE_WEIGHTS.values())
        cls.votes_score = round(sum(cls.vote_agreement.get(n, 0) * w for n, w in VOTE_WEIGHTS.items()) / total, 3)
    return cls


def _heuristic(ticket: Ticket, evidence: list[Evidence], reason: str) -> Classification:
    """Fallback when no model is selected or every model call fails. Deliberately simple."""
    top_card = next((e for e in evidence if e.kind == "service_card"), None)
    service = as_service(ticket.affected_service) or (as_service(top_card.title) if top_card else None)
    service = service or "Emailed Support Tickets"
    playbook = next((e for e in evidence if e.kind == "playbook" and e.title.startswith(service)), None)
    request = ticket.work_type == "Service Request"
    unclear = (ticket.request_type or "").lower().startswith("nonsense")
    extraction = Extraction(
        work_type="Service Request" if request else "Incident",
        service=service,
        scope="individual" if request else "one_entity",
        outage_extent="none" if request else "partial_degradation",
        workaround="not_applicable" if request else "none",
        regulatory_or_security=False,
        deadline_pressure="none",
        resolution="clarification" if unclear else "done",
        playbook_ref=playbook.ref_id if playbook else None,
        rationale=f"Heuristic fallback ({reason}): kept intake values.",
    )
    return Classification(extraction=extraction, heuristic=True, fallback_reason=reason)


def _vote(samples: list[Extraction]) -> tuple[Extraction, dict[str, float], float]:
    """Per-field majority; returns the merged extraction, per-field agreement and weighted score."""
    merged: dict = {}
    agreement: dict[str, float] = {}
    for name in VOTE_WEIGHTS:
        value, wins = Counter(getattr(s, name) for s in samples).most_common(1)[0]
        merged[name] = value
        agreement[name] = round(wins / len(samples), 3)
    # Rationale from a sample that agrees with the majority service.
    merged["rationale"] = next(s.rationale for s in samples if s.service == merged["service"])
    total = sum(VOTE_WEIGHTS.values())
    score = sum(agreement[n] * w for n, w in VOTE_WEIGHTS.items()) / total
    return Extraction(**merged), agreement, round(score, 3)


VoteUpdate = dict  # {"index": int, "ok": bool, "answer": dict | None, "error": str | None}


def classify_iter(
    ticket: Ticket, evidence: list[Evidence], model: str | None
) -> Generator[VoteUpdate, None, Classification]:
    """Yields each vote as it arrives (for the live walkthrough), returns the merged Classification."""
    if not model:
        return _apply_manual(ticket, _heuristic(ticket, evidence, "no LLM model selected"))

    prompt = _prompt(ticket, evidence)
    votes = max(1, settings.llm_votes)
    samples: list[Extraction] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=votes) as pool:
        futures = {pool.submit(llm.parse, SYSTEM_PROMPT, prompt, Extraction, model): i for i in range(votes)}
        for future in as_completed(futures):
            index = futures[future] + 1
            try:
                result = future.result()
                if result is None:
                    raise ValueError("empty response")
                samples.append(result)
                yield {"index": index, "ok": True, "answer": result.model_dump(), "error": None}
            except Exception as exc:  # one failed vote must not sink the ticket
                errors.append(f"{type(exc).__name__}: {exc}")
                yield {"index": index, "ok": False, "answer": None, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}

    if not samples:
        log.warning("All %d votes failed on %s: %s", votes, model, errors[:1])
        first = errors[0].split(":")[0] if errors else "no response"
        return _apply_manual(ticket, _heuristic(ticket, evidence, f"{model} failed: {first}"))

    extraction, agreement, score = _vote(samples)
    if extraction.playbook_ref and extraction.playbook_ref not in {e.ref_id for e in evidence}:
        extraction.playbook_ref = None  # never trust a reference that was not retrieved
    if len(samples) < votes:  # missing votes count as disagreement
        score = round(score * len(samples) / votes, 3)
    return _apply_manual(ticket, Classification(extraction=extraction, vote_agreement=agreement, votes_score=score))


def classify(ticket: Ticket, evidence: list[Evidence], model: str | None) -> Classification:
    it = classify_iter(ticket, evidence, model)
    while True:
        try:
            next(it)
        except StopIteration as stop:
            return stop.value
