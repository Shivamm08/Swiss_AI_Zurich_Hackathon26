"""Copilot grounding: what the chat assistant may answer from, and what it refuses.

1. Retrieve only RELEVANT knowledge (retrieve.search drops anything below the similarity floor).
2. Relevant knowledge found, or a ticket is open  -> answer from it, citing [ref_id]s.
3. Nothing relevant and no ticket                 -> a small structured AI call decides whether the
   question is about service-desk work or this app at all:
     - off-topic (weather, recipes, general coding…) -> fixed refusal, no answer is generated;
     - on-topic but not in the knowledge base       -> the model must say so and may only explain
                                                       how the app works (APP_GUIDE), never invent fixes.
"""

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ingest import ticket_text
from app.models import Ticket
from app.pipeline import llm, retrieve
from app.schemas import ChatTurn, Evidence

Grounding = Literal["sources", "ticket", "no_knowledge", "off_topic"]


APP_GUIDE = """HOW THIS APP WORKS (you may explain this without citations)
- Roles: Team Lead / Analyst (one per department) checks every AI proposal and dispatches it; Specialist does the
  work and marks it done with a closing note; Admin runs the system (knowledge base, intake, settings).
- Lifecycle: awaiting analyst -> assigned -> in progress / waiting for info -> done. Low-confidence or untriaged
  tickets wait in the shared Needs review queue. Only done tickets enter the knowledge base.
- Escalate raises attention one level up (specialist -> Team Lead / Analyst -> Admin); the department's analyst
  de-escalates. Hand back returns a ticket to the analyst to reassign (reason required).
- Priority is never chosen by the AI: rules turn the facts the AI reads into Impact and Urgency, and the official
  matrix gives Priority. The AI reads work type, service, facts and resolution; team is a lookup."""

SYSTEM_PROMPT = f"""You are Triage Copilot, the assistant inside the IT service-desk app of a pan-European asset manager.
Rules:
- Answer about services, past fixes and tickets ONLY from the RETRIEVED KNOWLEDGE and the TICKET. Cite every such
  fact inline as [ref_id], using only ref_ids that appear in RETRIEVED KNOWLEDGE.
- If RETRIEVED KNOWLEDGE says nothing relevant was found, say plainly that the knowledge base has no matching
  past fix or description, and suggest asking the owning team. Never guess a fix, a cause, a system or an ID.
- Stay on service-desk work and this app. Be concise: short paragraphs or bullets, plain language.

{APP_GUIDE}"""

OFF_TOPIC_REPLY = ("I can only help with service-desk work: tickets, our services and their past fixes, people and "
                   "workload, and how to use this app. Try asking about a ticket or a service.")

SCOPE_PROMPT = """Decide whether the user's latest message belongs in an internal IT service-desk assistant at an
asset manager. In scope: tickets, incidents, service requests, the company's IT and business services and systems,
past fixes, teams, workload, escalations, how to use the triage app, and greetings or thanks.
Out of scope: anything else (general knowledge, weather, cooking, writing code, personal advice, other companies)."""


class Scope(BaseModel):
    in_scope: bool


_REFERS_BACK = re.compile(r"\b(it|its|that|this|those|these|they|them|same)\b", re.I)


def is_follow_up(question: str) -> bool:
    """Short questions, or ones that start with "and/also…" or refer back ("it", "that"), continue the topic."""
    words = question.split()
    starts = words[0].lower().strip(",.") in {"and", "also", "so", "then", "but"} if words else False
    return len(words) <= 6 or starts or (len(words) <= 12 and bool(_REFERS_BACK.search(question)))


@dataclass
class Grounded:
    citations: list[Evidence]
    context: str
    grounding: Grounding


def ground(db: Session, turns: list[ChatTurn], ticket: Ticket | None, model: str | None) -> Grounded:
    question = turns[-1].content
    # A follow-up ("and who fixes it?") is searched together with the previous question; a new
    # question on its own, so an earlier topic can't leak its sources into an unrelated answer.
    previous = next((t.content for t in reversed(turns[:-1]) if t.role == "user"), "")
    query = f"{previous}\n{question}".strip() if previous and is_follow_up(question) else question
    context = ""
    if ticket:
        context = ticket_text(ticket)
        query = f"{query}\n{ticket.summary}\n{ticket.description}"
    citations = retrieve.search(db, query, k=5)
    if citations:
        return Grounded(citations, context, "sources")
    if ticket:
        return Grounded([], context, "ticket")
    try:
        conversation = "\n".join(f"{t.role}: {t.content}" for t in turns[-4:])
        verdict = llm.parse(SCOPE_PROMPT, conversation, Scope, model)
    except Exception:
        verdict = None
    if verdict is not None and not verdict.in_scope:
        return Grounded([], context, "off_topic")
    return Grounded([], context, "no_knowledge")


def user_message(question: str, g: Grounded) -> str:
    knowledge = "\n\n".join(f"[{c.ref_id}] {c.title}\n{c.snippet}" for c in g.citations) or (
        "(nothing relevant found in the knowledge base: say so, don't guess)")
    return f"{question}\n\nTICKET\n{g.context or '(none)'}\n\nRETRIEVED KNOWLEDGE\n{knowledge}"


def fallback_answer(g: Grounded) -> str:
    """No AI model configured: list the sources, or say there are none."""
    if not g.citations:
        return "No AI model is configured, and nothing in the knowledge base matches this question."
    return "No AI model is configured, so here are the most relevant sources:\n" + "\n".join(
        f"- [{c.ref_id}] {c.title}" for c in g.citations)
