"""Intake check for the New-ticket form: reject text that isn't a ticket at all.

Only clear non-tickets are rejected: keyboard mashing, test strings, requests that have nothing to do
with a service desk ("write me a poem"). Vague but real tickets ("cash not there pls fix asap") are
accepted: the pipeline routes them to clarification, which is the right handling for a real desk.

1. Rules (always, no AI): too few real words, or text that is mostly not letters.
2. AI (when a model is configured): one small structured call classifies ticket / vague / not_a_ticket.
Jira import and email are not checked here: a real inbox can't reject mail, and those tickets are
flagged downstream instead (unclear input -> low confidence -> Needs review).
"""

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.pipeline import llm

_WORD = re.compile(r"[A-Za-zÀ-ÿ]{2,}")
_VOWEL = re.compile(r"[aeiouyàâäéèêëîïôöùûü]", re.I)

PROMPT = """You screen new tickets for the IT service desk of an asset manager (trading, settlement, fund
accounting, reporting, market data, client services, office IT and access).
Classify the SUMMARY and DESCRIPTION:
- "ticket": a real problem or request, even if short, technical or badly written.
- "vague": plausibly real but missing detail (e.g. "pls fix asap", "system slow"). Still accepted.
- "not_a_ticket": random characters, keyboard mashing, placeholder or test text, or a request that has
  nothing to do with a service desk (jokes, poems, homework, general questions).
When in doubt between "vague" and "not_a_ticket", choose "vague"."""


class Verdict(BaseModel):
    verdict: Literal["ticket", "vague", "not_a_ticket"]
    reason: str = Field(description="One short sentence for the person who submitted it")


@dataclass
class Check:
    ok: bool
    verdict: str
    reason: str


def _looks_like_text(text: str) -> str | None:
    """Rule check; returns a reason when the text clearly isn't language."""
    words = [w for w in _WORD.findall(text) if _VOWEL.search(w)]
    letters = sum(c.isalpha() for c in text)
    visible = sum(not c.isspace() for c in text) or 1
    if len(words) < 3:
        return "It needs at least a few real words describing the problem or request."
    if letters / visible < 0.5:
        return "It's mostly symbols or numbers rather than a description."
    mashed = [w for w in words if re.search(r"(.)\1{3,}", w.lower())]
    if len(mashed) >= max(2, len(words) // 2):
        return "It looks like repeated characters rather than a description."
    return None


def check(summary: str, description: str, model: str | None) -> Check:
    text = f"{summary}\n{description}"
    if reason := _looks_like_text(text):
        return Check(False, "not_a_ticket", reason)
    try:
        verdict = llm.parse(PROMPT, f"SUMMARY: {summary}\nDESCRIPTION: {description}", Verdict, model)
    except Exception:
        verdict = None  # never block a ticket because the check itself failed
    if verdict is None:
        return Check(True, "ticket", "rules only")
    return Check(verdict.verdict != "not_a_ticket", verdict.verdict, verdict.reason)
