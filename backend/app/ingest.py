"""Map raw inputs (Jira export records, emails) onto Ticket columns."""

from datetime import datetime, timezone
from typing import Any

from app.domain import normalize_level
from app.models import Ticket


def _first(value: Any) -> str | None:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def jira_records(payload: Any) -> list[dict[str, Any]]:
    """Accepts the challenge export ({"records": [...]}) or the training file ([...])."""
    if isinstance(payload, dict):
        return list(payload.get("records", []))
    return list(payload)


def ticket_from_jira(record: dict[str, Any], source: str) -> Ticket:
    return Ticket(
        source=source,
        work_type=record.get("Work type"),
        request_type=record.get("Request type"),
        summary=record.get("Summary") or "(no summary)",
        description=record.get("Description") or "",
        affected_service=_first(record.get("Affected Business or IT Services")),
        business_entity=_first(record.get("Business Entity")),
        reporter=record.get("Reporter"),
        urgency=normalize_level(record.get("Urgency")),
        impact=normalize_level(record.get("Impact")),
        priority=normalize_level(record.get("Priority")),
        status=record.get("Status"),
        linked_issues=[str(x) for x in record.get("Linked issues") or []],
        comments=list(record.get("All Comments") or []),
        raw=record,
        source_created_at=_parse_date(record.get("Created date")),
    )


def ticket_from_email(from_address: str, subject: str, body: str, business_entity: str | None) -> Ticket:
    return Ticket(
        source="email",
        request_type="Email / 3rd Party Warning",
        summary=subject,
        description=body,
        business_entity=business_entity,
        reporter=from_address,
        status="open",
        comments=[],
        linked_issues=[],
        raw={},
    )


def ticket_text(ticket: Ticket) -> str:
    """Flatten a ticket into one text block for retrieval and prompting."""
    parts = [
        f"Summary: {ticket.summary}",
        f"Description: {ticket.description}",
        f"Request type: {ticket.request_type or '-'}",
        f"Intake service (may be wrong): {ticket.affected_service or '-'}",
        f"Business entity: {ticket.business_entity or '-'}",
        f"Reporter: {ticket.reporter or '-'}",
        f"Linked issues: {', '.join(ticket.linked_issues) or '-'}",
    ]
    if ticket.comments:
        parts.append("Comments:\n" + "\n".join(f"- {c}" for c in ticket.comments))
    return "\n".join(parts)
