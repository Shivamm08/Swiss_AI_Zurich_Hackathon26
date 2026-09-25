from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import validate_model
from app.db import SessionLocal, get_db
from app.ingest import ticket_text
from app.kb.sync import sync_kb
from app.models import KbDocument, Ticket
from app.pipeline import llm, retrieve
from app.schemas import (
    AssistantAnswer,
    AssistantRequest,
    CopilotEvent,
    CopilotRequest,
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

    try:
        answer = llm.complete(ASSISTANT_PROMPT, user, model)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{model} failed: {exc}") from exc
    if answer is None:
        answer = "No LLM model selected, so here are the most relevant sources:\n" + "\n".join(
            f"- [{c.ref_id}] {c.title}" for c in citations
        )
    return AssistantAnswer(answer=answer, citations=citations, model=llm.model_name(model))


COPILOT_PROMPT = """You are Triage Copilot, the assistant inside a service-desk app at a pan-European asset manager.
You help analysts and team leads with tickets, services, past resolutions and how this app works.
Ground factual answers about services and past fixes in the RETRIEVED KNOWLEDGE and cite it as [ref_id].
If a TICKET is given, answer about that ticket specifically. If the knowledge does not cover a question, say so
briefly and suggest who to ask (the owning team). Be concise: short paragraphs or bullet lists, plain language."""


@router.post(
    "/assistant/stream",
    response_class=StreamingResponse,
    responses={200: {"model": CopilotEvent, "content": {"text/event-stream": {}},
                     "description": "Server-sent events: one 'sources', many 'token', then 'done'"}},
)
def stream_copilot(body: CopilotRequest) -> StreamingResponse:
    """Copilot chat: retrieves knowledge for the latest question, then streams the answer token by token."""
    model = llm.resolve_model(validate_model(body.model))

    def events():
        def send(event: CopilotEvent) -> str:
            return f"data: {event.model_dump_json()}\n\n"

        with SessionLocal() as db:
            question = body.messages[-1].content
            context, query = "", question
            if body.ticket_id and (ticket := db.get(Ticket, body.ticket_id)):
                context = ticket_text(ticket)
                query = f"{question}\n{ticket.summary}\n{ticket.description}"
            citations = retrieve.search(db, query, k=5)
            yield send(CopilotEvent(type="sources", citations=citations))

            knowledge = "\n\n".join(f"[{c.ref_id}] {c.title}\n{c.snippet}" for c in citations)
            turns = [t.model_dump() for t in body.messages[-10:]]
            turns[-1]["content"] = f"{question}\n\nTICKET\n{context or '(none)'}\n\nRETRIEVED KNOWLEDGE\n{knowledge}"
            try:
                tokens = llm.stream_chat(COPILOT_PROMPT, turns, model)
                if tokens is None:
                    text = "No AI model is configured, so here are the most relevant sources:\n" + "\n".join(
                        f"- [{c.ref_id}] {c.title}" for c in citations)
                    yield send(CopilotEvent(type="token", text=text))
                else:
                    for token in tokens:
                        yield send(CopilotEvent(type="token", text=token))
                yield send(CopilotEvent(type="done", model=llm.model_name(model)))
            except Exception as exc:
                yield send(CopilotEvent(type="error", text=f"{model} failed: {str(exc)[:300]}"))

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
