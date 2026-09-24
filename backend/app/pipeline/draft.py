"""Step 5: write the resolution comment (the "G" in RAG), grounded on the
matched playbook entry and the ticket's own specifics."""

from app.ingest import ticket_text
from app.models import KbDocument, Ticket
from app.pipeline import llm
from app.pipeline.classify import Classification

SYSTEM_PROMPT = """You are the assigned L2 agent writing the closing comment on a Jira ticket.
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


def draft_comment(ticket: Ticket, cls: Classification, playbook_doc: KbDocument | None) -> str:
    reference = playbook_doc.content if playbook_doc else "(no matching playbook entry)"
    user = (
        f"TICKET\n{ticket_text(ticket)}\n\n"
        f"DECISION\nservice={cls.service} work_type={cls.work_type} resolution={cls.resolution}\n\n"
        f"REFERENCE RESOLUTION\n{reference}"
    )
    text = llm.complete(SYSTEM_PROMPT, user)
    if text:
        return text.strip()
    if playbook_doc and cls.resolution == "done":
        return playbook_doc.meta.get("note", playbook_doc.content)
    return _FALLBACK[cls.resolution].format(service=cls.service)
