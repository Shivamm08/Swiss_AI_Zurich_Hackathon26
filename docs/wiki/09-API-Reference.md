# 9 · API reference

All routes are under `/api`. With the app running, **http://localhost:8000/docs** shows every
endpoint with its exact request and response shapes, and lets you try them. The contract file is
`contracts/openapi.json`.

## System and reference

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | Database status, LLM provider and default model |
| GET | `/api/reference` | Services (with team and criticality), teams, levels, work types, resolutions, the priority matrix. Feeds all dropdowns |
| GET | `/api/llm/models` | Models for the picker: `{provider, default_model, models: [{id, label, provider}]}` |
| POST | `/api/reference/priority` | `{urgency, impact}` → `{priority}` |
| POST | `/api/rubric/preview` | `{facts, service, work_type}` → impact, urgency, priority, score, trace (what-if tool) |
| GET | `/api/settings` | Thresholds, SLA hours, votes, max share, default capacity (read-only) |

## Tickets

| Method | Path | What it does |
|---|---|---|
| GET | `/api/tickets` | The queue. Query: `view` (mine · team · needs_review · escalations · all), `as_user` (email), `sort` (priority_score · sla_due_at · confidence · number), `state`, `source`, `service`, `team`, `q` (search), `include_closed` (default false: closed tickets are hidden), `limit`, `offset` |
| POST | `/api/tickets` | Create a ticket. `summary`, `description` required; optional `manual` = staff-confirmed fields |
| POST | `/api/tickets/from-email` | `{from_address, subject, body, business_entity?}` → a new ticket |
| POST | `/api/tickets/import` | Upload a Jira export JSON (multipart: `file`, `source`) |
| GET | `/api/tickets/{id}` | Ticket + latest proposal + review history |
| DELETE | `/api/tickets/{id}` | Delete a ticket (and its proposals/reviews) |
| POST | `/api/tickets/{id}/assign` | `{assignee: email}`: set the working assignee |

## Triage and review

| Method | Path | What it does |
|---|---|---|
| GET | `/api/tickets/{id}/triage/stream?model=` | **Live triage** as server-sent events, one event per step |
| POST | `/api/tickets/{id}/triage` | Triage one ticket, return the proposal. Body `{model}` optional |
| POST | `/api/triage/batch` | `{ticket_ids?, source?, model?}`: triage many (default: all `new`) |
| GET | `/api/triage/{result_id}` | One proposal |
| POST | `/api/triage/{result_id}/review` | `{action: approve · edit · reject, edits?, reviewer, notes?, review_seconds?}` |

`model` is any id from `/api/llm/models`, or `heuristic` for no LLM. Unknown models get a `400`.

## Knowledge and assistant

| Method | Path | What it does |
|---|---|---|
| GET | `/api/kb/documents?kind=` | List knowledge documents (service_card · playbook · historical_ticket) |
| POST | `/api/kb/search` | `{query, k?, kinds?}` → ranked documents (test retrieval) |
| POST | `/api/kb/sync` | Reload the knowledge files into the database (+ embeddings) |
| POST | `/api/assistant/stream` | **Copilot**: `{messages: [{role, content}], ticket_id?, model?}` → server-sent events `sources`, `token`…, `done` |
| POST | `/api/assistant/ask` | Single-shot question → answer + citations (older, non-streaming) |

## Messaging and directory

| Method | Path | What it does |
|---|---|---|
| GET | `/api/chat/channels?as_user=` | Department channels + the person's direct messages, with the last message |
| GET | `/api/chat/messages?channel=` | Messages in a channel (oldest first) |
| POST | `/api/chat/messages` | `{channel, sender, body, kind?, ticket_id?}`; kind `escalation` also marks the ticket escalated |
| POST | `/api/chat/draft` | `{ticket_id, sender, to, purpose: escalate · handoff · question, model?}` → AI-drafted message + channel |
| GET | `/api/directory` | Departments with services, lead, members (with load), open tickets, escalations, activity |

## People and insights

| Method | Path | What it does |
|---|---|---|
| GET | `/api/users?team=` | The roster |
| GET | `/api/workload?team=` | Per-member load, share, escalations for one team |
| GET | `/api/metrics` | Acceptance / edit / reject rates, review time, routes, escalations, SLA breaches, priority before vs after |
| GET | `/api/metrics/calibration` | Confidence buckets → agreement with analysts |
| GET | `/api/metrics/impact?include_demo=&days=` | Pain-point numbers + daily series for the Impact dashboard |
| GET | `/api/export/submission?source=challenge` | Challenge-format JSON: the final decision if reviewed, else the latest proposal |

## Examples

```bash
# Create a ticket with two staff-confirmed fields, then watch it being triaged live
curl -s -X POST localhost:8000/api/tickets -H 'content-type: application/json' -d '{
  "summary": "FX forward confirmations not reaching the Nordics desk",
  "description": "Since the 09:00 run, confirmations for Nordics funds are missing.",
  "reporter": "desk@intcom.com", "business_entity": "Nordics",
  "linked_issues": [], "comments": [],
  "manual": {"service": "Trade Matching", "urgency": "High"}
}'

curl -N "localhost:8000/api/tickets/<id>/triage/stream?model=gpt-5.4-mini"
```

Stream output (one line per event; `data` depends on the step):

```
data: {"stage":"retrieve","status":"completed","elapsed_ms":413,"message":"Found 6 relevant documents","data":{"evidence":[…],"hybrid":true}}
data: {"stage":"vote","status":"completed","elapsed_ms":4618,"message":"Vote 3 answered","data":{"index":3,"ok":true,"answer":{…}}}
…
data: {"stage":"done","status":"completed","elapsed_ms":9416,"message":"Proposal ready in 9.4s","data":{"triage_result_id":"…"}}
```

| `stage` | `data` contains |
|---|---|
| retrieve | `evidence`, `hybrid` |
| vote | `index`, `ok`, `answer` or `error` |
| extract | `extraction`, `vote_agreement`, `votes_score`, `heuristic`, `manual` |
| rubric | `facts`, `impact`, `urgency`, `priority`, `priority_score`, `trace`, `critical` |
| confidence | `confidence`, `route`, `escalated`, `sla_due_at` |
| assign | `suggestion`, `working_assignee` |
| draft | `comment`, `reference` |
| done | `triage_result_id` |
| error | `detail` |

```bash
# Approve with an edit: team and priority are recomputed server-side
curl -s -X POST localhost:8000/api/triage/<result_id>/review -H 'content-type: application/json' \
  -d '{"action": "edit", "edits": {"urgency": "Low"}, "reviewer": "karen.brown@intcom.com", "review_seconds": 38}'
```
