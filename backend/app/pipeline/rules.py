"""Step 4: deterministic lookups. No LLM here, so these can never be inconsistent."""

from app.domain import Level, ServiceName, TeamName, priority_for, team_for
from app.models import KbDocument

# Fallback owner per service when no playbook entry matched.
# TODO: fill once Swiss Life confirms how assignees should be chosen for
# services that have no resolution notes in the training data.
ASSIGNEE_FALLBACK: dict[str, str] = {}


def team(service: ServiceName) -> TeamName:
    return team_for(service)


def priority(urgency: Level, impact: Level) -> Level:
    return priority_for(urgency, impact)


def assignee(service: ServiceName, playbook_doc: KbDocument | None) -> str | None:
    if playbook_doc and playbook_doc.meta.get("resolver"):
        return playbook_doc.meta["resolver"]
    return ASSIGNEE_FALLBACK.get(service)
