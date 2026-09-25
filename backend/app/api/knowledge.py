from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import validate_model
from app.db import SessionLocal, get_db
from app.kb.sync import sync_kb
from app.models import KbDocument, Ticket
from app.pipeline import copilot, llm, retrieve
from app.schemas import (
    AssistantAnswer,
    AssistantRequest,
    ChatTurn,
    CopilotEvent,
    CopilotRequest,
    Evidence,
    EvidenceKind,
    KbDocumentOut,
    KbSearchRequest,
    KbSyncResult,
)

router = APIRouter(tags=["knowledge"])

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
    """One-shot Copilot answer (same grounding and scope rules as the chat)."""
    model = llm.resolve_model(validate_model(body.model))
    ticket = db.get(Ticket, body.ticket_id) if body.ticket_id else None
    turns = [ChatTurn(role="user", content=body.question)]
    g = copilot.ground(db, turns, ticket, model)
    if g.grounding == "off_topic":
        return AssistantAnswer(answer=copilot.OFF_TOPIC_REPLY, citations=[], model=llm.model_name(model), grounding="off_topic")
    try:
        answer = llm.complete(copilot.SYSTEM_PROMPT, copilot.user_message(body.question, g), model)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{model} failed: {exc}") from exc
    return AssistantAnswer(answer=answer or copilot.fallback_answer(g), citations=g.citations,
                           model=llm.model_name(model), grounding=g.grounding)


@router.post(
    "/assistant/stream",
    response_class=StreamingResponse,
    responses={200: {"model": CopilotEvent, "content": {"text/event-stream": {}},
                     "description": "Server-sent events: one 'sources', many 'token', then 'done'"}},
)
def stream_copilot(body: CopilotRequest) -> StreamingResponse:
    """Copilot chat: retrieves relevant knowledge for the latest question (refusing off-topic questions),
    then streams the answer token by token. See app/pipeline/copilot.py."""
    model = llm.resolve_model(validate_model(body.model))

    def events():
        def send(event: CopilotEvent) -> str:
            return f"data: {event.model_dump_json()}\n\n"

        with SessionLocal() as db:
            ticket = db.get(Ticket, body.ticket_id) if body.ticket_id else None
            g = copilot.ground(db, body.messages, ticket, model)
            yield send(CopilotEvent(type="sources", citations=g.citations, grounding=g.grounding))
            if g.grounding == "off_topic":  # refused: nothing is generated
                yield send(CopilotEvent(type="token", text=copilot.OFF_TOPIC_REPLY))
                yield send(CopilotEvent(type="done", model=llm.model_name(model), grounding=g.grounding))
                return
            turns = [t.model_dump() for t in body.messages[-10:]]
            turns[-1]["content"] = copilot.user_message(body.messages[-1].content, g)
            try:
                tokens = llm.stream_chat(copilot.SYSTEM_PROMPT, turns, model)
                if tokens is None:
                    yield send(CopilotEvent(type="token", text=copilot.fallback_answer(g)))
                else:
                    for token in tokens:
                        yield send(CopilotEvent(type="token", text=token))
                yield send(CopilotEvent(type="done", model=llm.model_name(model), grounding=g.grounding))
            except Exception as exc:
                yield send(CopilotEvent(type="error", text=f"{model} failed: {str(exc)[:300]}"))

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
