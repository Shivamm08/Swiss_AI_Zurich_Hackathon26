"""Step 5: write the resolution comment (the "G" in RAG), grounded on the
matched playbook entry and the ticket's own specifics."""

from app.ingest import ticket_text
from app.models import KbDocument, Ticket
from app.pipeline import llm
from app.pipeline.classify import Extraction

SYSTEM_PROMPT = """You are the assigned L2 agent writing the closing comment on a Jira ticket, in the first person.
Write 1-3 sentences starting with "Resolution:". Follow root cause -> action -> verification.
Reuse the reference resolution's approach but use this ticket's specifics (IDs, entity, counts, systems).
If the resolution status is "clarification", instead state exactly what information is missing.
Only use facts from the TICKET and the REFERENCE RESOLUTION: never invent systems, IDs, causes or actions.
No filler such as "issue fixed"."""

# Without a matching past fix there is nothing true to report yet, so the draft is a plan, not a
# resolution: writing "I fixed X" here would be a hallucination.
NO_PRECEDENT_PROMPT = """No past resolution matches this ticket: it's a new kind of problem.
Write "No matching past fix. Suggested first steps:" followed by 2-3 short numbered steps an L2 agent
should take to diagnose it, using only facts from the TICKET and the service. Never claim that anything
was found, done or fixed. If the resolution status is "clarification", list exactly what to ask the reporter."""

NO_PRECEDENT_FALLBACK = ("No matching past fix. Suggested first steps: 1) Confirm scope and timing with the reporter. "
                         "2) Check {service} logs and monitoring for the reported window. 3) Escalate to the {service} "
                         "owners if the cause isn't clear.")

_FALLBACK = {
    "done": "Resolution: Validated the reported behaviour on {service}, applied the standard remediation and confirmed normal operation with the reporter.",
    "clarification": "Resolution: Requested clarification from the reporter; the ticket does not state the affected {service} process, timeframe or expected outcome.",
    "cannot reproduce": "Resolution: Re-checked {service} logs and monitoring for the reported window; the symptom could not be reproduced and no further errors were observed.",
    "cancelled": "Resolution: Closed as no action required on {service}; the request was withdrawn or duplicated an existing ticket.",
}


def draft_comment(
    ticket: Ticket, cls: Extraction, reference_doc: KbDocument | None, model: str | None, assignee: str | None = None
) -> str:
    """`reference_doc` is the matched playbook entry, or a resolved past ticket (learning loop).
    Without one, the draft is a list of first steps instead of a (made-up) resolution."""
    user = (
        f"TICKET\n{ticket_text(ticket)}\n\n"
        f"DECISION\nservice={cls.service} work_type={cls.work_type} resolution={cls.resolution} "
        f"assigned_agent={assignee or 'unassigned'}"
        + (f"\n\nREFERENCE RESOLUTION\n{reference_doc.content}" if reference_doc else "")
    )
    try:
        text = llm.complete(SYSTEM_PROMPT if reference_doc else NO_PRECEDENT_PROMPT, user, model)
    except Exception:  # keep the proposal usable if the model call fails
        text = None
    if text:
        return text.strip()
    if reference_doc and cls.resolution == "done":
        return reference_doc.meta.get("note", reference_doc.content)
    if reference_doc is None:
        return NO_PRECEDENT_FALLBACK.format(service=cls.service)
    return _FALLBACK[cls.resolution].format(service=cls.service)
