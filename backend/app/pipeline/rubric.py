"""Deterministic policy: extracted facts + service criticality -> Impact, Urgency,
Priority and a continuous 0..1 priority score.

Ported from the feature/apertus-triage branch (data/triage/rubric.py). No model
runs here: every value is a table lookup taken from the challenge matrix's own
row/column definitions, so the policy is readable, testable and can never break
the matrix. Each decision also returns a plain-language reason for the UI.
"""

from dataclasses import dataclass, field

from app.domain import SERVICE_CATALOG, Level, priority_for
from app.schemas import Facts

PRIORITY_BANDS: dict[Level, tuple[float, float]] = {
    "Lowest": (0.00, 0.20),
    "Low": (0.20, 0.40),
    "Medium": (0.40, 0.60),
    "High": (0.60, 0.80),
    "Highest": (0.80, 1.00),
}

# Sub-signals that order tickets *within* a priority band. Weights sum to 1.
SEVERITY_WEIGHTS = {
    "service_critical": 0.25,
    "regulatory_or_security": 0.25,
    "no_workaround": 0.20,
    "full_outage": 0.15,
    "broad_scope": 0.10,
    "hard_deadline": 0.05,
}

# Within-band offset. The "difficulty" factor from the original is off: resolution
# time is random in this data, so its weight is redistributed (0.60/0.25 -> 0.7059/0.2941).
OFFSET_WEIGHTS = {"severity": 0.60 / 0.85, "age": 0.25 / 0.85}
AGE_SATURATION_DAYS = 120.0
_BAND_MARGIN = 0.02

BROAD_SCOPE = frozenset({"multi_entity", "external_counterparty"})
NARROW_SCOPE = frozenset({"individual", "team"})


@dataclass
class RubricResult:
    impact: Level
    urgency: Level
    priority: Level
    priority_score: float
    severity: float
    critical: bool
    trace: list[str] = field(default_factory=list)


def is_critical(service: str) -> bool:
    return SERVICE_CATALOG.get(service, ("", "Non-Critical"))[1] == "Critical"  # type: ignore[arg-type]


def classify_impact(f: Facts, critical: bool, is_request: bool) -> tuple[Level, str]:
    """Impact from the matrix's column definitions."""
    if f.outage_extent == "none" or (is_request and f.outage_extent != "full_unavailability"):
        return "Lowest", "no service degradation (informational or a request)"
    if critical:
        if f.outage_extent == "full_unavailability":
            return "Highest", "critical service fully unavailable"
        return "High", "critical service partially degraded"
    if f.scope in BROAD_SCOPE:
        return "High", "non-critical service, several entities or external counterparties affected"
    if f.outage_extent == "full_unavailability":
        return "Medium", "non-critical service fully unavailable"
    if f.scope in NARROW_SCOPE:
        return "Low", "non-critical service, only an individual or team affected"
    return "Medium", "non-critical service, up to one business entity affected"


def classify_urgency(f: Facts, critical: bool, is_request: bool) -> tuple[Level, str]:
    """Urgency from the matrix's row definitions (first match wins)."""
    if f.regulatory_or_security and f.workaround == "none":
        return "Highest", "regulatory/security breach with no workaround"
    if critical and f.outage_extent == "full_unavailability":
        return "Highest", "critical service fully down"
    if f.workaround == "difficult":
        return "High", "only a difficult workaround exists"
    if critical and f.deadline_pressure == "hard":
        return "High", "critical service with a hard deadline"
    if f.regulatory_or_security:
        return "High", "regulatory/security implication"
    if is_request or f.outage_extent == "none":
        if f.deadline_pressure == "none":
            return "Lowest", "routine request, no operational effect"
        return "Low", "routine request with some time pressure"
    if f.workaround == "easy":
        return "Medium", "an easy workaround exists"
    if f.outage_extent == "partial_degradation":
        if critical:
            return "Medium", "partial degradation on a critical service"
        return "Low", "partial degradation on a non-critical service"
    return "Low", "handled in normal workflow"


def severity_offset(f: Facts, critical: bool) -> float:
    signals = {
        "service_critical": critical,
        "regulatory_or_security": f.regulatory_or_security,
        "no_workaround": f.workaround == "none",
        "full_outage": f.outage_extent == "full_unavailability",
        "broad_scope": f.scope in BROAD_SCOPE,
        "hard_deadline": f.deadline_pressure == "hard",
    }
    return round(sum(w for name, w in SEVERITY_WEIGHTS.items() if signals[name]), 4)


def age_factor(age_days: float | None, resolved: bool) -> float:
    if resolved or age_days is None or age_days <= 0:
        return 0.0
    return min(1.0, age_days / AGE_SATURATION_DAYS)


def priority_score(priority: Level, offset: float) -> float:
    """Continuous 0..1 rank that never leaves the priority's band."""
    low, high = PRIORITY_BANDS[priority]
    pad = (high - low) * _BAND_MARGIN
    span = (high - low) - 2 * pad
    return round(low + pad + span * max(0.0, min(1.0, offset)), 4)


def apply_rubric(
    facts: Facts, service: str, work_type: str, age_days: float | None = None, resolved: bool = False
) -> RubricResult:
    critical = is_critical(service)
    is_request = work_type == "Service Request"
    impact, impact_why = classify_impact(facts, critical, is_request)
    urgency, urgency_why = classify_urgency(facts, critical, is_request)
    priority = priority_for(urgency, impact)
    severity = severity_offset(facts, critical)
    offset = OFFSET_WEIGHTS["severity"] * severity + OFFSET_WEIGHTS["age"] * age_factor(age_days, resolved)
    return RubricResult(
        impact=impact,
        urgency=urgency,
        priority=priority,
        priority_score=priority_score(priority, offset),
        severity=severity,
        critical=critical,
        trace=[
            f"Impact {impact}: {impact_why}",
            f"Urgency {urgency}: {urgency_why}",
            f"Priority {priority} = matrix[urgency {urgency}][impact {impact}]",
        ],
    )


def rescore(old_priority: Level, old_score: float | None, new_priority: Level) -> float | None:
    """Keep a ticket's position within its band when an analyst changes the priority."""
    if old_score is None or old_priority == new_priority:
        return old_score
    low, high = PRIORITY_BANDS[old_priority]
    pad = (high - low) * _BAND_MARGIN
    offset = (old_score - low - pad) / ((high - low) - 2 * pad)
    return priority_score(new_priority, offset)
