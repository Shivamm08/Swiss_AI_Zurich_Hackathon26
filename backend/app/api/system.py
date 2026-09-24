from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.config import settings
from app.db import get_db
from app.domain import (
    IMPACT_LABELS,
    LEVELS,
    PRIORITY_MATRIX,
    RESOLUTIONS,
    SERVICE_CATALOG,
    TEAMS,
    URGENCY_LABELS,
    WORK_TYPES,
    priority_for,
)
from app.pipeline import llm
from app.schemas import Health, LlmModels, PriorityRequest, PriorityResponse, ReferenceData, ServiceInfo

router = APIRouter(tags=["system"])


@router.get("/health", response_model=Health)
def get_health(db: Session = Depends(get_db)) -> Health:
    try:
        db.execute(text("select 1"))
        database = True
    except Exception:
        database = False
    return Health(
        status="ok" if database else "degraded",
        database=database,
        llm_provider=settings.llm_provider,
        llm_model=settings.chat_model,
        llm_configured=settings.llm_configured,
        embeddings_configured=settings.embeddings_configured,
        version=__version__,
    )


@router.get("/reference", response_model=ReferenceData)
def get_reference() -> ReferenceData:
    return ReferenceData(
        services=[ServiceInfo(name=n, team=t, criticality=c) for n, (t, c) in SERVICE_CATALOG.items()],
        teams=list(TEAMS),
        levels=list(LEVELS),
        work_types=list(WORK_TYPES),
        resolutions=list(RESOLUTIONS),
        urgency_labels=URGENCY_LABELS,
        impact_labels=IMPACT_LABELS,
        priority_matrix=PRIORITY_MATRIX,
    )


@router.get("/llm/models", response_model=LlmModels)
def list_llm_models() -> LlmModels:
    return LlmModels(
        provider=settings.llm_provider,
        default_model=settings.chat_model,
        models=list(llm.available_models()),
    )


@router.post("/reference/priority", response_model=PriorityResponse)
def compute_priority(body: PriorityRequest) -> PriorityResponse:
    return PriorityResponse(priority=priority_for(body.urgency, body.impact))
