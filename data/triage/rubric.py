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

# Keeps a score strictly inside its band so sorting by score never disagrees
# with sorting by the categorical priority.
_BAND_MARGIN = 0.02

BROAD_SCOPE = frozenset({"multi_entity", "external_counterparty"})
NARROW_SCOPE = frozenset({"individual", "team"})


def classify_impact(evidence: dict, service_is_critical: bool) -> str:
    """Impact from the matrix's own column definitions."""
    outage = evidence["outage_extent"]
    scope = evidence["scope"]

    # No service degradation at all -> informational / no direct impact.
    if outage == "none" or (evidence["is_request"] and outage != "full_unavailability"):
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

    if evidence["is_request"] or outage == "none":
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


def apply_rubric(evidence: dict, service: str) -> dict:
    """Full deterministic pass for one ticket."""
    critical = config.is_critical(service)
    impact = classify_impact(evidence, critical)
    urgency = classify_urgency(evidence, critical)
    priority = PRIORITY_MATRIX[urgency][impact]
    offset = severity_offset(evidence, critical)
    return {
        "impact_pred": impact,
        "urgency_pred": urgency,
        "priority_pred": priority,
        "priority_score": priority_score(priority, offset),
        "severity_offset": round(offset, 4),
        "service_is_critical": critical,
        "service_unresolvable": service in config.UNRESOLVABLE_SERVICES,
    }
