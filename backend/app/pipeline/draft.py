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
No filler such as "issue fixed"."""

_FALLBACK = {
    "done": "Resolution: Validated the reported behaviour on {service}, applied the standard remediation and confirmed normal operation with the reporter.",
    "clarification": "Resolution: Requested clarification from the reporter; the ticket does not state the affected {service} process, timeframe or expected outcome.",
    "cannot reproduce": "Resolution: Re-checked {service} logs and monitoring for the reported window; the symptom could not be reproduced and no further errors were observed.",
    "cancelled": "Resolution: Closed as no action required on {service}; the request was withdrawn or duplicated an existing ticket.",
}


def draft_comment(
    ticket: Ticket, cls: Extraction, reference_doc: KbDocument | None, model: str | None, assignee: str | None = None
) -> str:
    """`reference_doc` is the matched playbook entry, or an approved past ticket (learning loop)."""
    reference = reference_doc.content if reference_doc else "(no matching past resolution)"
    user = (
        f"TICKET\n{ticket_text(ticket)}\n\n"
        f"DECISION\nservice={cls.service} work_type={cls.work_type} resolution={cls.resolution} "
        f"assigned_agent={assignee or 'unassigned'}\n\n"
        f"REFERENCE RESOLUTION\n{reference}"
    )
    try:
        text = llm.complete(SYSTEM_PROMPT, user, model)
    except Exception:  # keep the proposal usable if the model call fails
        text = None
    if text:
        return text.strip()
    if reference_doc and cls.resolution == "done":
        return reference_doc.meta.get("note", reference_doc.content)
    return _FALLBACK[cls.resolution].format(service=cls.service)
