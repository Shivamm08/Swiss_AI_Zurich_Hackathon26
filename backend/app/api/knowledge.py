from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import validate_model
from app.db import get_db
from app.ingest import ticket_text
from app.kb.sync import sync_kb
from app.models import KbDocument, Ticket
from app.pipeline import llm, retrieve
from app.schemas import (
    AssistantAnswer,
    AssistantRequest,
    Evidence,
    EvidenceKind,
    KbDocumentOut,
    KbSearchRequest,
    KbSyncResult,
)

router = APIRouter(tags=["knowledge"])

ASSISTANT_PROMPT = """You are a copilot for service desk analysts at a pan-European asset manager.
Answer using ONLY the retrieved knowledge below. Cite sources inline as [ref_id].
If the knowledge does not cover the question, say so."""


def _doc_out(doc: KbDocument) -> KbDocumentOut:
    return KbDocumentOut(
        id=doc.id,
        kind=doc.kind,  # type: ignore[arg-type]
        ref_id=doc.ref_id,
        title=doc.title,
        content=doc.content,
        meta=doc.meta,
        has_embedding=doc.embedding is not None,
    )


@router.get("/kb/documents", response_model=list[KbDocumentOut])
def list_kb_documents(kind: EvidenceKind | None = None, db: Session = Depends(get_db)) -> list[KbDocumentOut]:
    stmt = select(KbDocument).order_by(KbDocument.kind, KbDocument.ref_id)
    if kind:
        stmt = stmt.where(KbDocument.kind == kind)
    return [_doc_out(d) for d in db.scalars(stmt)]


@router.post("/kb/search", response_model=list[Evidence])
def search_kb(body: KbSearchRequest, db: Session = Depends(get_db)) -> list[Evidence]:
    return retrieve.search(db, body.query, k=body.k, kinds=body.kinds)


@router.post("/kb/sync", response_model=KbSyncResult)
def sync_knowledge_base(db: Session = Depends(get_db)) -> KbSyncResult:
    synced, embedded = sync_kb(db)
    return KbSyncResult(synced=synced, embedded=embedded)


@router.post("/assistant/ask", response_model=AssistantAnswer)
def ask_assistant(body: AssistantRequest, db: Session = Depends(get_db)) -> AssistantAnswer:
    model = llm.resolve_model(validate_model(body.model))
    query = body.question
    context = ""
    if body.ticket_id and (ticket := db.get(Ticket, body.ticket_id)):
        context = ticket_text(ticket)
        query = f"{body.question}\n{ticket.summary}\n{ticket.description}"

    citations = retrieve.search(db, query, k=5)
    knowledge = "\n\n".join(f"[{c.ref_id}] {c.title}\n{c.snippet}" for c in citations)
    user = f"QUESTION\n{body.question}\n\nTICKET\n{context or '(none)'}\n\nRETRIEVED KNOWLEDGE\n{knowledge}"

    answer = llm.complete(ASSISTANT_PROMPT, user, model)
    if answer is None:
        answer = "No LLM model selected, so here are the most relevant sources:\n" + "\n".join(
            f"- [{c.ref_id}] {c.title}" for c in citations
        )
    return AssistantAnswer(answer=answer, citations=citations, model=llm.model_name(model))
