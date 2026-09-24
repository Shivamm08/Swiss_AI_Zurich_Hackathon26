"""Evidence schema extracted by Apertus, plus the ordinal vocabularies.

The schema is deliberately enums-and-booleans only. A free-text field was
tried and removed: under vLLM guided decoding it intermittently ran away
(hundreds of newlines) or truncated mid-string, breaking the JSON. The
constrained fields have never failed. Source text for auditing comes from the
corpus itself, which is more trustworthy than a model-generated quote anyway.

Only rubric-relevant facts are extracted. The model never names an Impact,
Urgency or Priority itself -- that mapping lives in ``rubric.py`` so it stays
deterministic and auditable.
"""

from __future__ import annotations

# Ordinal vocabulary used by the Jira dataset for both Impact and Urgency.
ORDINALS = ("lowest", "low", "medium", "high", "highest")

SCOPE = ("individual", "team", "one_entity", "multi_entity", "external_counterparty")
OUTAGE = ("none", "partial_degradation", "full_unavailability")
WORKAROUND = ("none", "difficult", "easy", "not_applicable")
DEADLINE = ("none", "soft", "hard")
# Work type is a first-class predicted field, using the dataset's own vocabulary.
WORK_TYPE = ("Incident", "Service Request")

# Fields decided by majority vote across N_VOTES samples.
VOTED_FIELDS = (
    "work_type",
    "scope",
    "outage_extent",
    "workaround",
    "regulatory_or_security",
    "deadline_pressure",
)

EVIDENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "work_type": {
            "type": "string",
            "enum": list(WORK_TYPE),
            "description": (
                "'Incident' when an IT service is interrupted, degraded, "
                "erroring, delayed or behaving unexpectedly -- including "
                "monitoring alerts and third-party warnings about a service. "
                "'Service Request' when a user asks for something to be "
                "provided or withdrawn (access, licence, provisioning, "
                "information) and nothing is broken."
            ),
        },
        "scope": {
            "type": "string",
            "enum": list(SCOPE),
            "description": (
                "Breadth of who is affected. 'individual' one person; 'team' a "
                "single team; 'one_entity' one country/business entity; "
                "'multi_entity' more than one; 'external_counterparty' external "
                "financial counterparties or clients are affected."
            ),
        },
        "outage_extent": {
            "type": "string",
            "enum": list(OUTAGE),
            "description": (
                "'none' the service still works or this is informational; "
                "'partial_degradation' slow, delayed or intermittently failing; "
                "'full_unavailability' the service cannot be used at all."
            ),
        },
        "workaround": {
            "type": "string",
            "enum": list(WORKAROUND),
            "description": (
                "'none' no workaround; 'difficult' one exists but is slow or "
                "manual; 'easy' a simple workaround exists; 'not_applicable' "
                "for service requests where nothing is broken."
            ),
        },
        "regulatory_or_security": {
            "type": "boolean",
            "description": (
                "True only if the ticket implies a regulatory/compliance breach "
                "or a security compromise, not merely that a regulated system "
                "is involved."
            ),
        },
        "deadline_pressure": {
            "type": "string",
            "enum": list(DEADLINE),
            "description": (
                "'hard' a dated cutoff will be missed (NAV cutoff, settlement "
                "date, regulatory filing); 'soft' time matters but no cutoff; "
                "'none' no time pressure stated."
            ),
        },
    },
    "required": [
        "work_type",
        "scope",
        "outage_extent",
        "workaround",
        "regulatory_or_security",
        "deadline_pressure",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are an experienced L2 IT service desk agent at a pan-European asset "
    "manager. You read a Jira ticket and report the observable facts needed to "
    "triage it. Work through the steps in order.\n\n"
    "STEP 1 - work_type. Is something broken, or is someone asking for "
    "something?\n"
    "  'Incident': an IT service is interrupted, degraded, erroring, delayed "
    "or behaving unexpectedly. Monitoring alerts, third-party warnings about "
    "a service, and reported disruptions are all Incidents.\n"
    "  'Service Request': someone asks for something to be provided or "
    "withdrawn -- a licence, an account, access rights, a provisioning "
    "action, or information. Nothing is broken.\n"
    "  Judge this from the description body. Titles are misleading on purpose.\n"
    "  MALFORMED TICKETS: some tickets are unclear, incomplete or misrouted "
    "and report no fault at all. Do not default these to Incident. Classify "
    "them by the workflow the text says they deviate from: a malformed "
    "'incident note' is still an 'Incident', whereas text that does not match "
    "the expected 'service request pattern', or that is a general/unclear "
    "enquiry, is a 'Service Request' to be redirected or rejected.\n\n"
    "STEP 2 - outage_extent. This follows directly from Step 1.\n"
    "  If Service Request: nothing is down. Use 'none'.\n"
    "  If Incident: something IS wrong, so NEVER use 'none'.\n"
    "    'full_unavailability' only when the text says the service is "
    "completely unusable, fully down, or totally blocked.\n"
    "    'partial_degradation' for everything else -- monitoring alerts, "
    "execution errors, processing delays, degraded performance, feed delays, "
    "and any alert that asks someone to confirm the impact. This is the "
    "normal answer for an incident.\n\n"
    "STEP 3 - workaround.\n"
    "  If Service Request: 'not_applicable'.\n"
    "  If Incident: 'easy' if the text offers a simple alternative, "
    "'difficult' if the alternative is manual or slow, 'none' if the text "
    "gives no way around the fault. Do not invent a workaround that the "
    "ticket does not mention.\n\n"
    "STEP 4 - scope. Pick the narrowest the text actually supports.\n"
    "  'individual' one named person (typical for access/licence requests).\n"
    "  'team' one team or desk.\n"
    "  'one_entity' a whole country or business entity, OR a shared "
    "platform service whose failure is not limited to named users. A "
    "monitoring alert on a shared business system is normally 'one_entity'.\n"
    "  'multi_entity' more than one country/entity is implicated.\n"
    "  'external_counterparty' external clients or financial counterparties "
    "are affected, including warnings sent in by a third party.\n\n"
    "STEP 5 - regulatory_or_security: true ONLY for an actual regulatory "
    "breach or security compromise, not because a regulated system is "
    "involved.\n\n"
    "STEP 6 - deadline_pressure: 'hard' only if a dated cutoff will be missed "
    "(NAV cutoff, settlement date, filing deadline); 'soft' if time matters "
    "without a stated cutoff; otherwise 'none'.\n\n"
    "Worked examples:\n"
    "  'X generated an automated monitoring alert... repeated execution "
    "errors, service degradation, or a processing delay. Please review the "
    "event, confirm the impact.' -> work_type='Incident', "
    "outage_extent='partial_degradation', workaround='none', "
    "scope='one_entity', deadline_pressure='none'.\n"
    "  'A new user requires a licence for X... needs validation before the "
    "entitlement is assigned.' -> work_type='Service Request', "
    "outage_extent='none', workaround='not_applicable', scope='individual'.\n"
    "  'A third party sent a warning regarding X. The email references a "
    "delayed feed or degraded service performance.' -> work_type='Incident', "
    "outage_extent='partial_degradation', "
    "scope='external_counterparty'.\n"
    "  'The incident note for X is not aligned with the expected service "
    "context and contains malformed or unrelated information.' -> "
    "work_type='Incident' (it is a malformed incident note), "
    "outage_extent='partial_degradation'.\n"
    "  'The ticket text for X is unclear and not aligned with the expected "
    "service request pattern. The message appears incomplete or misrouted.' "
    "-> work_type='Service Request' (it fails the service request pattern), "
    "outage_extent='none', workaround='not_applicable'.\n\n"
    "Report only what the ticket says. Do not inflate severity. Answer with "
    "JSON only."
)


def build_user_prompt(summary: str, description: str, service: str, comments: str) -> str:
    parts = [
        f"Summary: {summary}",
        f"Description: {description}",
        f"Affected service (as recorded, may be wrong): {service}",
    ]
    if comments:
        parts.append(f"Investigation comments:\n{comments}")
    parts.append("\nReport the triage evidence as JSON.")
    return "\n".join(parts)
