"""API contract. Every request/response body lives here.

The frontend's TypeScript types are generated from these models
(contracts/openapi.json -> frontend/src/api/schema.d.ts). After changing this
file run `make contract` and commit both generated files.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config import LlmProvider
from app.domain import Criticality, Level, Resolution, ServiceName, TeamName, WorkType

TicketSource = Literal["challenge", "training", "manual", "email", "demo"]
TriageState = Literal["new", "proposed", "approved", "edited", "rejected"]
ReviewAction = Literal["approve", "edit", "reject"]
EvidenceKind = Literal["service_card", "playbook", "historical_ticket"]
Route = Literal["auto", "review", "triage"]
# admin: runs the system · analyst: team lead who checks the AI triage and dispatches · specialist: does the work
Role = Literal["admin", "analyst", "specialist"]
# open: waiting for an analyst · assigned: dispatched to a specialist · in_progress · waiting (for information) · done
WorkStatus = Literal["open", "assigned", "in_progress", "waiting", "done"]
WorkAction = Literal["start", "wait", "resume", "resolve", "handback"]
# inbox: the analyst's department, waiting for their decision · needs_review: untriaged or low confidence (any analyst)
TicketView = Literal["mine", "inbox", "team", "needs_review", "escalations", "all"]

# Observable facts the LLM extracts (enums/booleans only); the rubric turns them into Impact/Urgency.
Scope = Literal["individual", "team", "one_entity", "multi_entity", "external_counterparty"]
Outage = Literal["none", "partial_degradation", "full_unavailability"]
Workaround = Literal["none", "difficult", "easy", "not_applicable"]
Deadline = Literal["none", "soft", "hard"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Facts(BaseModel):
    scope: Scope = Field(description="Who is affected: one person up to external counterparties")
    outage_extent: Outage
    workaround: Workaround
    regulatory_or_security: bool = Field(description="Actual regulatory breach or security compromise")
    deadline_pressure: Deadline


# ---------------------------------------------------------------- system


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    llm_provider: LlmProvider
    llm_model: str | None
    llm_configured: bool
    embeddings_configured: bool
    version: str


class ServiceInfo(BaseModel):
    name: ServiceName
    team: TeamName
    criticality: Criticality


class ReferenceData(BaseModel):
    """Everything the UI needs for dropdowns, labels and the priority matrix."""

    services: list[ServiceInfo]
    teams: list[TeamName]
    levels: list[Level]
    work_types: list[WorkType]
    resolutions: list[Resolution]
    urgency_labels: dict[Level, str]
    impact_labels: dict[Level, str]
    priority_matrix: dict[Level, dict[Level, Level]] = Field(
        description="priority_matrix[urgency][impact] -> priority"
    )


Provider = Literal["azure", "openai", "apertus"]


class ModelOption(BaseModel):
    id: str = Field(description="Send this as `model` in triage/assistant requests")
    label: str
    provider: Provider


class LlmModels(BaseModel):
    provider: LlmProvider = Field(description="Main provider (Apertus is listed in `models` when configured)")
    default_model: str | None
    models: list[ModelOption] = Field(description="Choices for the model picker ('heuristic' is always allowed too)")


class PriorityRequest(BaseModel):
    urgency: Level
    impact: Level


class PriorityResponse(BaseModel):
    priority: Level


# ---------------------------------------------------------------- tickets


class TicketBase(BaseModel):
    work_type: str | None = None
    request_type: str | None = None
    summary: str
    description: str = ""
    affected_service: str | None = Field(None, description="Intake value; may be wrong")
    business_entity: str | None = None
    reporter: str | None = None
    urgency: str | None = None
    impact: str | None = None
    priority: str | None = None
    status: str | None = "open"
    linked_issues: list[str] = []
    comments: list[str] = []


class ManualFields(BaseModel):
    """Values staff fill in themselves. The pipeline keeps them and only fills the gaps."""

    work_type: WorkType | None = None
    service: ServiceName | None = None
    urgency: Level | None = None
    impact: Level | None = None
    assignee: str | None = None
    resolution: Resolution | None = None
    resolution_comment: str | None = None


class TicketCreate(TicketBase):
    """New-ticket form: summary, description and reporter are required; anything in `manual`
    is confirmed by staff, everything else is derived by the pipeline."""

    summary: str = Field(min_length=3)
    description: str = Field(min_length=3)
    source: TicketSource = "manual"
    manual: ManualFields | None = None
    created_by: str = Field(description="Email of the Team Lead / Analyst or admin creating it (specialists can't)")


class EmailIngest(BaseModel):
    from_address: str
    subject: str
    body: str
    business_entity: str | None = None


class TicketOut(TicketBase, ORM):
    id: uuid.UUID
    number: int
    source: TicketSource
    triage_state: TriageState
    source_created_at: datetime | None
    created_at: datetime
    # Working assignment + fields flattened from the latest proposal, so the queue needs one call.
    assignee: str | None = None
    ai_service: str | None = None
    ai_team: str | None = None
    ai_priority: str | None = None
    priority_score: float | None = None
    confidence: float | None = None
    route: Route | None = None
    escalated: bool = False
    sla_due_at: datetime | None = None
    manual_fields: list[str] = Field(default=[], description="Fields confirmed by staff at creation")
    work_status: WorkStatus = "open"
    resolution: str | None = Field(None, description="Set by the specialist when the ticket is done")
    resolution_comment: str | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None


TriageStage = Literal["retrieve", "extract", "vote", "rubric", "confidence", "assign", "draft", "done", "error"]


class TriageStreamEvent(BaseModel):
    """One step of the live triage walkthrough (GET /api/tickets/{id}/triage/stream, server-sent events).

    `data` per stage: retrieve -> {evidence, hybrid} · vote -> {index, ok, answer, error} ·
    extract -> {extraction, vote_agreement, votes_score, heuristic, manual} ·
    rubric -> {facts, impact, urgency, priority, priority_score, trace, critical} ·
    confidence -> {confidence, route, escalated, sla_due_at} · assign -> {suggestion, working_assignee} ·
    draft -> {comment, reference} · done -> {triage_result_id} · error -> {detail}
    """

    stage: TriageStage
    status: Literal["started", "completed", "failed"]
    elapsed_ms: int
    message: str
    data: dict[str, Any] = {}


class TicketPage(BaseModel):
    items: list[TicketOut]
    total: int


class ImportResult(BaseModel):
    imported: int
    skipped: int


# ---------------------------------------------------------------- triage


class Evidence(BaseModel):
    kind: EvidenceKind
    ref_id: str
    title: str
    snippet: str
    score: float = Field(description="Hybrid rank score, normalised so the best hit = 1.0 (ordering only)")
    similarity: float | None = Field(None, description="Cosine similarity to the query (absolute relevance); None without embeddings")


class Decision(BaseModel):
    """The seven fields the challenge scores, plus Urgency/Impact."""

    work_type: WorkType
    service: ServiceName
    team: TeamName
    assignee: str | None
    urgency: Level
    impact: Level
    priority: Level
    resolution: Resolution
    resolution_comment: str


class StaffCheck(BaseModel):
    """A value staff set that the independent check disagrees with. Staff's value is kept; the
    analyst sees the disagreement before dispatching."""

    field: str
    staff: str = Field(description="What staff entered (kept)")
    checked: str = Field(description="What the independent check found")
    by: Literal["ai", "rules"] = Field(description="ai: the blind AI reading (votes); rules: the rubric / roster")
    note: str


class ConfidenceOut(BaseModel):
    overall: float = Field(ge=0, le=1, description="min(votes, retrieval) x flag multipliers")
    votes: float = Field(description="How consistently the model answered across votes")
    retrieval: float = Field(description="How closely the matched past solution fits")
    flags: list[str] = Field(description="Reasons for caution, e.g. generic_service, unclear_input, staff_disagreement")
    staff_checks: list[StaffCheck] = Field(default=[], description="Staff-set values the AI reading or the rules disagree with")


class AssigneeCandidate(BaseModel):
    user: str
    name: str
    score: float
    open: int
    capacity: int
    expertise: float


class AssigneeSuggestion(BaseModel):
    expert: str | None = Field(description="Resolver of the matched playbook entry (used for the export)")
    recommended: str | None = Field(description="Best candidate after workload balancing")
    reason: str
    candidates: list[AssigneeCandidate]


class TriageResultOut(Decision, ORM):
    id: uuid.UUID
    ticket_id: uuid.UUID
    confidence: float = Field(ge=0, le=1, description="Overall confidence (same as confidence_detail.overall)")
    confidence_detail: ConfidenceOut | None = None
    facts: Facts | None = None
    priority_score: float | None = None
    rubric_trace: list[str] = []
    vote_agreement: dict[str, float] = {}
    route: Route | None = None
    escalated: bool = False
    sla_due_at: datetime | None = None
    assignee_suggestion: AssigneeSuggestion | None = None
    playbook_ref: str | None = None
    rationale: str
    evidence: list[Evidence]
    changed_fields: list[str] = Field(description="Fields that differ from the intake values")
    model: str
    latency_ms: int
    created_at: datetime


class TriageRequest(BaseModel):
    model: str | None = Field(None, description="LLM model from /api/llm/models; omit for the default, 'heuristic' for no LLM")


class BatchTriageRequest(BaseModel):
    ticket_ids: list[uuid.UUID] | None = Field(None, description="Omit to triage every ticket in state 'new'")
    source: TicketSource | None = None
    model: str | None = Field(None, description="LLM model from /api/llm/models; omit for the default, 'heuristic' for no LLM")


class BatchTriageResult(BaseModel):
    triaged: int
    failed: int


class DecisionEdit(BaseModel):
    """Analyst overrides. Team and priority are always recomputed server-side
    from service and urgency/impact, so they can never be inconsistent."""

    work_type: WorkType | None = None
    service: ServiceName | None = None
    assignee: str | None = None
    urgency: Level | None = None
    impact: Level | None = None
    resolution: Resolution | None = None
    resolution_comment: str | None = None


class ReviewCreate(BaseModel):
    action: ReviewAction
    edits: DecisionEdit | None = None
    reviewer: str
    notes: str | None = None
    review_seconds: float | None = Field(None, description="Time the analyst spent, measured by the UI")


class ReviewOut(ORM):
    id: uuid.UUID
    ticket_id: uuid.UUID
    triage_result_id: uuid.UUID
    action: ReviewAction
    final: Decision | None
    overridden_fields: list[str]
    reviewer: str
    notes: str | None
    review_seconds: float | None
    created_at: datetime


class AssignRequest(BaseModel):
    assignee: str = Field(description="A specialist in the ticket's department")
    by: str = Field(description="The Team Lead / Analyst or admin doing it")


class TicketNote(BaseModel):
    by: str
    note: str | None = None


class RubricPreviewRequest(BaseModel):
    facts: Facts
    service: ServiceName
    work_type: WorkType


class RubricPreview(BaseModel):
    impact: Level
    urgency: Level
    priority: Level
    priority_score: float
    rubric_trace: list[str]


class ActivityEntry(BaseModel):
    at: datetime
    by: str
    action: str = Field(description="triaged | approved | edited | rejected | assigned | start | wait | resume | resolve | "
                                     "handback | escalated | deescalated")
    note: str | None = None


class WorkUpdate(BaseModel):
    """A specialist moving their ticket along: start -> (wait -> resume) -> resolve (done), or
    handback: give it back to the department's analyst to reassign (note required)."""

    action: WorkAction
    by: str = Field(description="Email of the person acting (the assigned specialist, or an admin)")
    note: str | None = Field(None, description="What information is missing (wait), or why you're handing it back (handback)")
    resolution: Resolution | None = Field(None, description="Required for resolve")
    resolution_comment: str | None = Field(None, description="Required for resolve: root cause, action taken, verification")


class TicketDetail(TicketOut):
    latest_triage: TriageResultOut | None
    reviews: list[ReviewOut]
    activity: list[ActivityEntry] = []


# ---------------------------------------------------------------- knowledge base / RAG


class KbDocumentOut(ORM):
    id: uuid.UUID
    kind: EvidenceKind
    ref_id: str
    title: str
    content: str
    meta: dict[str, Any]
    has_embedding: bool


class KbSearchRequest(BaseModel):
    query: str
    k: int = Field(5, ge=1, le=20)
    kinds: list[EvidenceKind] | None = None


class KbSyncResult(BaseModel):
    synced: int
    embedded: int


class AssistantRequest(BaseModel):
    question: str
    ticket_id: uuid.UUID | None = Field(None, description="Ground the answer in this ticket as well")
    model: str | None = Field(None, description="LLM model from /api/llm/models; omit for the default, 'heuristic' for no LLM")


class AssistantAnswer(BaseModel):
    answer: str
    citations: list[Evidence]
    model: str
    grounding: Literal["sources", "ticket", "no_knowledge", "off_topic"] = "sources"


# ---------------------------------------------------------------- metrics


class Metrics(BaseModel):
    tickets_total: int
    by_state: dict[TriageState, int]
    reviews_total: int
    acceptance_rate: float | None = Field(description="approved / reviewed")
    edit_rate: float | None
    reject_rate: float | None
    avg_review_seconds: float | None
    avg_confidence: float | None
    field_override_counts: dict[str, int] = Field(description="How often analysts changed each field")
    by_route: dict[str, int] = Field(description="Latest proposals per route (auto/review/triage)")
    escalations_open: int
    sla_breaches: int = Field(description="Open tickets past their SLA deadline")
    priority_intake: dict[str, int] = Field(description="Priority as submitted")
    priority_ai: dict[str, int] = Field(description="Priority after triage")


class CalibrationBucket(BaseModel):
    low: float
    high: float
    reviewed: int
    agreement: float | None = Field(description="Share approved without changing service or priority")


class Calibration(BaseModel):
    buckets: list[CalibrationBucket]
    note: str


# ---------------------------------------------------------------- people / workload


class UserOut(ORM):
    email: str
    name: str
    role: Role
    teams: list[str]
    capacity: int


class WorkloadMember(BaseModel):
    email: str
    name: str
    role: Role
    open: int
    capacity: int
    share: float = Field(description="Share of the team's open tickets")
    high_open: int = Field(description="Open tickets with priority High or Highest")
    oldest_open_at: datetime | None
    resolved_7d: int = Field(description="Tickets this person closed in the last 7 days")


class Workload(BaseModel):
    team: str
    open_total: int
    members: list[WorkloadMember]
    escalations: list[TicketOut]


class SettingsOut(BaseModel):
    auto_threshold: float
    triage_threshold: float
    sla_hours: dict[Level, float]
    votes: int
    max_share: float
    default_capacity: int


# ---------------------------------------------------------------- messaging / directory

ChannelKind = Literal["team", "dm"]
# resolved: the automatic "ticket done" note a specialist's Team Lead / Analyst receives
MessageKind = Literal["message", "system", "escalation", "handoff", "resolved"]
# Hand-offs are not a message any more: a specialist hands a ticket back (POST /tickets/{id}/work).
DraftPurpose = Literal["escalate", "question"]


class MessageOut(ORM):
    id: uuid.UUID
    channel: str
    sender: str
    sender_name: str
    body: str
    kind: MessageKind
    ticket_id: uuid.UUID | None
    ticket_number: int | None = None
    ticket_summary: str | None = None
    created_at: datetime


class MessageCreate(BaseModel):
    channel: str = Field(description='"team:<Team>" or "dm:<email>|<email>" (any order)')
    sender: str
    body: str = Field(min_length=1)
    kind: MessageKind = "message"
    ticket_id: uuid.UUID | None = Field(None, description="Attach a ticket; kind 'escalation' also marks it escalated")


class ChannelOut(BaseModel):
    id: str
    kind: ChannelKind
    title: str
    subtitle: str
    members: list[str]
    last_message: MessageOut | None
    message_count: int


class DraftRequest(BaseModel):
    ticket_id: uuid.UUID
    sender: str
    to: str = Field(description="A person's email, or 'team:<Team>'")
    purpose: DraftPurpose = "escalate"
    model: str | None = None


class DraftOut(BaseModel):
    channel: str
    recipient_label: str
    body: str
    kind: MessageKind
    model: str


class MemberBrief(BaseModel):
    email: str
    name: str
    role: Role
    open: int
    capacity: int


class ServiceBrief(BaseModel):
    name: ServiceName
    criticality: Criticality


class Department(BaseModel):
    team: TeamName
    channel: str
    services: list[ServiceBrief]
    lead: MemberBrief | None
    members: list[MemberBrief]
    open_tickets: int
    escalations: int
    messages_7d: int


# ---------------------------------------------------------------- copilot chat


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CopilotRequest(BaseModel):
    messages: list[ChatTurn] = Field(min_length=1, description="Conversation so far; the last one is the question")
    ticket_id: uuid.UUID | None = None
    model: str | None = None


class CopilotEvent(BaseModel):
    """Server-sent event of POST /api/assistant/stream: sources first, then tokens, then done."""

    type: Literal["sources", "token", "done", "error"]
    text: str | None = None
    citations: list[Evidence] = []
    model: str | None = None
    grounding: Literal["sources", "ticket", "no_knowledge", "off_topic"] | None = Field(
        None, description="On 'sources' and 'done': what the answer rests on. off_topic = refused, nothing generated")


# ---------------------------------------------------------------- impact / trends


class DailyPoint(BaseModel):
    day: str
    created: int
    triaged: int
    approved: int
    edited: int
    rejected: int
    auto: int
    review: int
    triage: int
    misroutes: int = Field(description="Proposals whose service differs from the intake service")
    avg_review_seconds: float | None
    acceptance_rate: float | None


class Impact(BaseModel):
    include_demo: bool
    tickets: int
    tickets_triaged: int
    misroutes_caught: int
    priority_corrected: int
    clarifications_requested: int
    escalations: int
    auto_routed_share: float | None
    acceptance_rate: float | None
    avg_triage_seconds: float | None
    avg_review_seconds: float | None
    minutes_saved: float
    manual_triage_minutes: float
    max_load: float | None = Field(description="Busiest person's open tickets divided by their capacity")
    over_capacity: int = Field(description="People at or over capacity")
    learned_documents: int
    days: list[DailyPoint]
