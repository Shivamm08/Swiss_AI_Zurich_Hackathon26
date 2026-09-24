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

TicketSource = Literal["challenge", "training", "manual", "email"]
TriageState = Literal["new", "proposed", "approved", "edited", "rejected"]
ReviewAction = Literal["approve", "edit", "reject"]
EvidenceKind = Literal["service_card", "playbook", "historical_ticket"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


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


class TicketCreate(TicketBase):
    source: TicketSource = "manual"


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
    score: float


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


class TriageResultOut(Decision, ORM):
    id: uuid.UUID
    ticket_id: uuid.UUID
    confidence: float = Field(ge=0, le=1)
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


class TicketDetail(TicketOut):
    latest_triage: TriageResultOut | None
    reviews: list[ReviewOut]


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
