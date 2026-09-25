# 4 · Triage pipeline: one ticket, step by step

Code: `backend/app/pipeline/pipeline.py` (`triage_events`). Each step below emits a live event
that the ticket screen shows as it happens.

## Overview

| Step | Name | Done by | Output |
|---|---|---|---|
| 1 | Retrieve precedent | search (code + embeddings) | 6 most relevant knowledge documents |
| 2 | Read the ticket | LLM, 3 votes | work type, service, 5 facts, resolution status, matching document |
| 3 | Decide priority | code | impact, urgency, priority, 0–1 score, plain-language reasons |
| 4 | Measure confidence | code | confidence parts, route, escalation, SLA deadline |
| 5 | Route to a person | code | expert, recommended assignee, candidates |
| 6 | Draft the resolution | LLM | resolution comment |
| 7 | Save | code | a `triage_results` row; queue fields copied onto the ticket |

Total time: about 3–10 seconds with an OpenAI model, depending on the model.

## What the AI sees

The ticket is turned into plain text (`ingest.ticket_text`):

```
Summary: …
Description: …
Request type: …                      (e.g. "Machine Created Alert", strong hint)
Intake service (may be wrong): …
Business entity: …   Reporter: …   Linked issues: …
Comments: …
```

## Step 1: Retrieve precedent

The ticket text is embedded once and searched in two ways:
- **Keyword search (BM25):** rewards rare exact words like `MT536`, `SCD_POS_SYNC`, `SSI`.
- **Meaning search (vectors):** finds "cash shortfall" when the document says "missing balance".

The two rankings are merged, and the top 6 documents come back with a score (best = 1.00).
Details: [Knowledge base and RAG](07-Knowledge-Base-and-RAG.md).

## Step 2: Read the ticket (3 votes)

The LLM gets the ticket, the 6 documents and a **numbered procedure**. It's asked for
**observable facts only**, never a priority:

| Field | Values | Meaning |
|---|---|---|
| `work_type` | Incident · Service Request | Is something broken, or is someone asking for something? Judged from the body, not the title |
| `service` | one of 20 | Which service is really affected (the service cards give the boundaries) |
| `scope` | individual · team · one_entity · multi_entity · external_counterparty | Who is affected |
| `outage_extent` | none · partial_degradation · full_unavailability | How broken |
| `workaround` | none · difficult · easy · not_applicable | Is there a way around it |
| `regulatory_or_security` | true/false | Only for an actual breach, not just "a regulated system" |
| `deadline_pressure` | none · soft · hard | Will a dated cutoff be missed |
| `resolution` | done · clarification · cannot reproduce · cancelled | How it will likely be closed |
| `playbook_ref` | a retrieved document id or null | Which past solution matches |
| `rationale` | ≤ 2 sentences | Why (shown to the analyst) |

The answer is forced into this exact shape (OpenAI "structured outputs"), so it can't invent values.

**Voting:** the same request is sent **3 times in parallel**. For each field the majority
answer wins, and we record the agreement (3/3 = 100%, 2/3 = 67%). The agreement feeds the
confidence score. A reference the model names is only accepted if it was actually retrieved.

**Staff-confirmed fields:** if someone filled in work type, service or resolution when
creating the ticket, the prompt says "CONFIRMED BY STAFF: keep these values". They also
override the votes and count as 100% agreement.

**If the model fails** (no key, all 3 calls error), the system falls back to **heuristic mode**:
it keeps the intake values, uses defaults for the facts, and sets confidence to 20%. The reason
is shown on the ticket.

## Step 3: Decide priority

Fixed rules turn the facts plus the service's criticality into Impact and Urgency, then the
matrix gives Priority. Staff-set urgency/impact replace the rule result for that field.
Full tables and the score formula: [Priority and confidence](05-Priority-and-Confidence.md).

Example output shown to the analyst:

```
Impact High: critical service partially degraded
Urgency Medium: partial degradation on a critical service
Priority High = matrix[urgency Medium][impact High]
```

## Step 4: Measure confidence

`overall = min(vote agreement, past-case match) × warning flags`, then the route:
`auto` (≥ 80%), `review` (50–80%), `triage` (< 50%). Highest priority on a critical service is
**escalated** to the team lead. The SLA deadline is set from the priority.
Details: [Priority and confidence](05-Priority-and-Confidence.md#confidence).

## Step 5: Route to a person

- **Expert:** the author of the matched past solution. Saved as the proposal's assignee and used in the challenge export.
- **Recommended:** the best team member once workload is considered. Becomes the ticket's
  working assignee, unless the route is `triage` (then nobody until a human classifies it).
- A staff-chosen assignee always wins.

Details: [Assignment and workload](06-Assignment-and-Workload.md).

## Step 6: Draft the resolution

A second LLM call writes 1–3 sentences starting with `Resolution:`, in the first person as the
assigned agent, following **root cause → action → verification**. It adapts the matched past
solution using this ticket's details (IDs, entity, counts). If the status is `clarification`,
it states exactly what information is missing. A staff-written comment is used as-is. Without a
model, the matched note (or a fixed template) is used.

## Step 7: Save

A new `triage_results` row stores everything above: decision, facts, trace, vote agreement,
confidence breakdown, route, SLA, assignee suggestion, evidence, model and timing. Re-running
triage adds a new row; the latest one is shown. For fast queue sorting, these fields are copied
onto the ticket: `ai_service`, `ai_team`, `ai_priority`, `priority_score`, `confidence`, `route`,
`escalated`, `sla_due_at`, `assignee`. The ticket's state becomes `proposed`.

If the ticket has just become **escalated** (Highest on a critical service), an automatic
escalation message is posted to the owning team's channel ([Collaboration](13-Collaboration-and-Copilot.md#automatic-escalation)).

## After triage: the human decision

`POST /api/triage/{result_id}/review` with one of:

| Action | Effect |
|---|---|
| **approve** | The proposal becomes final. State `approved`. Added to the knowledge base (learning loop) |
| **edit** | The analyst's changes are applied; team and priority are **recomputed** from service and urgency/impact, so they can't become inconsistent. State `edited`. Added to the knowledge base |
| **reject** | State `rejected`, route set back to `triage`, assignee cleared. The ticket goes to Needs review |

The time spent (`review_seconds`) and the changed fields are recorded; the dashboard uses them.

## Three ways to run it

| How | Endpoint | Used by |
|---|---|---|
| Live, step by step | `GET /api/tickets/{id}/triage/stream` (server-sent events) | Ticket screen: ▶ Triage / Re-run live |
| One ticket, no streaming | `POST /api/tickets/{id}/triage` | Scripts, tests |
| Many tickets | `POST /api/triage/batch` | Intake & export → Batch triage |

All three accept a `model` (from the picker), or `heuristic` to run without an LLM.
