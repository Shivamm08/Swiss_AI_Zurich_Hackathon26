"""Step 6-7: confidence from measured signals, then routing and SLA.

overall = min(votes, retrieval) x flag multipliers.  See spec section 6.
"""

from datetime import datetime, timedelta

from app.config import settings
from app.domain import Level
from app.schemas import ConfidenceOut, Route

# Cosine similarity of text-embedding-3-small between a ticket and its matched past
# solution, rescaled to 0..1. Tune on the evaluation set.
SIM_FLOOR, SIM_CEIL = 0.30, 0.70
NO_MATCH_CAP = 0.30
KEYWORD_MATCH_SCORE = 0.60  # when embeddings are unavailable but a playbook entry matched

FLAG_MULTIPLIERS = {
    "generic_service": 0.6,   # resolved to the "Emailed Support Tickets" bucket
    "unclear_input": 0.7,     # request type says the input is nonsense / unclear
}
HEURISTIC_OVERALL = 0.2

SLA_HOURS: dict[Level, float] = {"Highest": 1, "High": 4, "Medium": 24, "Low": 72, "Lowest": 120}


def retrieval_score(similarity: float | None, matched: bool) -> float:
    if not matched:
        return NO_MATCH_CAP if similarity is None else min(NO_MATCH_CAP, _rescale(similarity))
    if similarity is None:
        return KEYWORD_MATCH_SCORE
    return _rescale(similarity)


def _rescale(similarity: float) -> float:
    return round(max(0.0, min(1.0, (similarity - SIM_FLOOR) / (SIM_CEIL - SIM_FLOOR))), 3)


def score(votes: float, retrieval: float, flags: list[str], heuristic: bool) -> ConfidenceOut:
    if heuristic:
        return ConfidenceOut(overall=HEURISTIC_OVERALL, votes=0.0, retrieval=retrieval, flags=["heuristic_fallback", *flags])
    overall = min(votes, retrieval)
    for flag in flags:
        overall *= FLAG_MULTIPLIERS.get(flag, 1.0)
    return ConfidenceOut(overall=round(overall, 3), votes=votes, retrieval=retrieval, flags=flags)


def route_for(overall: float) -> Route:
    if overall >= settings.auto_threshold:
        return "auto"
    if overall >= settings.triage_threshold:
        return "review"
    return "triage"


def sla_due(received_at: datetime, priority: Level) -> datetime:
    """The SLA clock starts when the ticket reaches the desk."""
    return received_at + timedelta(hours=SLA_HOURS[priority])
