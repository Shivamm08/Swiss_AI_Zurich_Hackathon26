"""Deterministic mapping: evidence + service criticality -> Impact, Urgency,
Priority, and a continuous 0..1 priority score.

No model runs here. Every value is a table lookup, so the whole policy is
readable, testable, and guaranteed consistent with the challenge matrix.
"""

from __future__ import annotations

from . import config

# Impact / Urgency are emitted in the dataset's own ordinal vocabulary
# (lowest..highest) so predictions sit alongside the recorded columns.
#
# Ordinal      Matrix column (Impact)          Matrix row (Urgency)
# highest  ->  Major / Widespread              Critical
# high     ->  Significant / Large             High
# medium   ->  Moderate / Limited              Medium
# low      ->  Minor / Localized               Low
# lowest   ->  No direct impact / Information  Lowest

PRIORITY_MATRIX = {
    # urgency -> impact -> priority
    "highest": {"highest": "highest", "high": "highest", "medium": "high", "low": "medium", "lowest": "medium"},
    "high": {"highest": "highest", "high": "high", "medium": "high", "low": "medium", "lowest": "low"},
    "medium": {"highest": "high", "high": "high", "medium": "medium", "low": "low", "lowest": "low"},
    "low": {"highest": "medium", "high": "medium", "medium": "low", "low": "low", "lowest": "lowest"},
    "lowest": {"highest": "medium", "high": "low", "medium": "low", "low": "lowest", "lowest": "lowest"},
}

PRIORITY_BANDS = {
    "lowest": (0.00, 0.20),
    "low": (0.20, 0.40),
    "medium": (0.40, 0.60),
    "high": (0.60, 0.80),
    "highest": (0.80, 1.00),
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

# The within-band offset blends hard severity with two soft factors: how long
# an unresolved ticket has been waiting, and how hard its peer group has
# historically been to resolve. Weights sum to 1.
OFFSET_WEIGHTS = {
    "severity": 0.60,
    "age": 0.25,
    "difficulty": 0.15,
}

# An unresolved ticket reaches the full age boost after this long. Chosen to
# span the corpus (tickets run Jan-Aug), so age spreads rather than saturating.
AGE_SATURATION_DAYS = 120.0

# Keeps a score strictly inside its band so sorting by score never disagrees
# with sorting by the categorical priority.
_BAND_MARGIN = 0.02

BROAD_SCOPE = frozenset({"multi_entity", "external_counterparty"})
NARROW_SCOPE = frozenset({"individual", "team"})


def is_request(evidence: dict) -> bool:
    """Whether the ticket is a Service Request rather than an Incident."""
    return evidence.get("work_type") == "Service Request"


def classify_impact(evidence: dict, service_is_critical: bool) -> str:
    """Impact from the matrix's own column definitions."""
    outage = evidence["outage_extent"]
    scope = evidence["scope"]

    # No service degradation at all -> informational / no direct impact.
    if outage == "none" or (is_request(evidence) and outage != "full_unavailability"):
        return "lowest"

    if service_is_critical:
        if outage == "full_unavailability":
            return "highest"  # Major / Widespread
        return "high"  # Significant / Large: partial loss of a critical service

    # Non-critical service from here on.
    if scope in BROAD_SCOPE:
        return "high"  # 1+ business entities or counterparties affected
    if outage == "full_unavailability":
        return "medium"  # Moderate / Limited
    if scope in NARROW_SCOPE:
        return "low"  # Minor / Localized
    return "medium"  # up to one business entity affected


def classify_urgency(evidence: dict, service_is_critical: bool) -> str:
    """Urgency from the matrix's own row definitions."""
    outage = evidence["outage_extent"]
    workaround = evidence["workaround"]
    deadline = evidence["deadline_pressure"]
    regulatory = evidence["regulatory_or_security"]

    if regulatory and workaround == "none":
        return "highest"
    if service_is_critical and outage == "full_unavailability":
        return "highest"

    if workaround == "difficult":
        return "high"
    if service_is_critical and deadline == "hard":
        return "high"
    if regulatory:
        return "high"

    if is_request(evidence) or outage == "none":
        # Routine provisioning with no operational effect.
        return "lowest" if deadline == "none" else "low"

    if workaround == "easy":
        return "medium"
    if outage == "partial_degradation":
        return "medium" if service_is_critical else "low"
    return "low"


def severity_offset(evidence: dict, service_is_critical: bool) -> float:
    """Weighted 0..1 blend of escalating sub-signals, used within a band."""
    signals = {
        "service_critical": service_is_critical,
        "regulatory_or_security": bool(evidence["regulatory_or_security"]),
        "no_workaround": evidence["workaround"] == "none",
        "full_outage": evidence["outage_extent"] == "full_unavailability",
        "broad_scope": evidence["scope"] in BROAD_SCOPE,
        "hard_deadline": evidence["deadline_pressure"] == "hard",
    }
    return sum(weight for name, weight in SEVERITY_WEIGHTS.items() if signals[name])


def age_factor(age_days: float | None, resolved: bool) -> float:
    """How much a ticket's time in the queue should escalate it, 0..1.

    Only unresolved tickets age: a closed ticket has no waiting cost. Ramps
    linearly to 1.0 at AGE_SATURATION_DAYS so a long-open ticket outranks a
    fresh one of identical severity, without ever leaving its priority band.
    """
    if resolved or age_days is None or age_days <= 0:
        return 0.0
    return min(1.0, age_days / AGE_SATURATION_DAYS)


def combined_offset(
    severity: float, age: float, difficulty: float | None = None
) -> float:
    """Blend severity with the soft factors into a single 0..1 offset.

    ``difficulty`` is None when the corpus provides no usable resolution-time
    signal. Its weight is then redistributed across the remaining factors
    rather than feeding random noise into the ranking.
    """
    weights = dict(OFFSET_WEIGHTS)
    parts = {"severity": severity, "age": age}

    if difficulty is None:
        spare = weights.pop("difficulty")
        total = sum(weights.values())
        for name in weights:
            weights[name] += spare * weights[name] / total
    else:
        parts["difficulty"] = difficulty

    return max(0.0, min(1.0, sum(weights[n] * parts[n] for n in weights)))


def priority_score(priority: str, offset: float) -> float:
    """Continuous 0..1 rank. Monotone with the categorical priority.

    The band fixes the coarse position (so the score can never contradict the
    matrix); the offset orders tickets inside that band, which is what makes a
    20k-row queue sortable by a single number.
    """
    low, high = PRIORITY_BANDS[priority]
    pad = (high - low) * _BAND_MARGIN
    span = (high - low) - 2 * pad
    return round(low + pad + span * max(0.0, min(1.0, offset)), 4)


def apply_rubric(
    evidence: dict,
    service: str,
    age_days: float | None = None,
    resolved: bool = True,
    difficulty: float | None = None,
) -> dict:
    """Full deterministic pass for one ticket.

    ``age_days`` and ``difficulty`` are the soft factors; both only move a
    ticket *within* its matrix-determined band, so Priority stays consistent.
    """
    critical = config.is_critical(service)
    impact = classify_impact(evidence, critical)
    urgency = classify_urgency(evidence, critical)
    priority = PRIORITY_MATRIX[urgency][impact]

    severity = severity_offset(evidence, critical)
    age = age_factor(age_days, resolved)
    offset = combined_offset(severity, age, difficulty)

    return {
        "work_type_pred": "Service Request" if is_request(evidence) else "Incident",
        "impact_pred": impact,
        "urgency_pred": urgency,
        "priority_pred": priority,
        "priority_score": priority_score(priority, offset),
        "severity_offset": round(severity, 4),
        "age_factor": round(age, 4),
        "difficulty_factor": None if difficulty is None else round(difficulty, 4),
        "combined_offset": round(offset, 4),
        "service_is_critical": critical,
        "service_unresolvable": service in config.UNRESOLVABLE_SERVICES,
    }
