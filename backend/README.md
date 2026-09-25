# Backend

FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 on PostgreSQL with pgvector. It runs the triage
pipeline, the Copilot, the ticket lifecycle and messaging, and serves every route under `/api`.
See the [root README](../README.md) for running the whole app, and the [wiki](../docs/wiki/Home.md)
for how it works.

```
app/
  main.py             FastAPI app, routers, startup
  config.py           every setting (read from .env)
  domain.py           fixed facts: 20 services, 11 teams, criticality, the priority matrix
  schemas.py          the API contract (every request / response model)
  models.py           database tables (tickets, triage_results, reviews, kb_documents, users, messages)
  ingest.py           Jira record / email -> ticket; ticket -> text for the AI
  chat.py             messaging helpers (channels, posting, escalation logging)
  api/
    deps.py           who may do what (get_actor, can_manage, can_escalate, require_creator)
    tickets.py        queue views, create (intake check), dispatch, work (start/wait/resume/done/hand back),
                      reopen, de-escalate, delete
    triage.py         run / stream / batch triage, the analyst's decision (approve, edit, reject)
    knowledge.py      knowledge base, search, Copilot (chat stream)
    insights.py       metrics, calibration, Impact + desk KPIs, challenge-set statistics, submission export
    people.py         users, team workload
    chat.py           channels, messages, AI-drafted escalations, directory
    system.py         health, reference data, models, settings
  pipeline/
    pipeline.py       the steps in order, yielding live events for the walkthrough
    retrieve.py       hybrid search (BM25 + pgvector), relevance filter (>= 40% similar)
    classify.py       the AI reading: 3 votes, structured output, blind to staff values
    rubric.py         facts -> impact, urgency, priority, 0-1 score
    confidence.py     confidence, flags, routing, SLA
    assignment.py     expert vs suggested specialist, workload
    draft.py          resolution draft (or first steps when no past fix matches)
    copilot.py        Copilot grounding: relevant sources, scope filter, app guide
    intake_check.py   rejects New-ticket text that isn't a ticket
    rules.py          team lookup, expert from the matched document
    llm.py            OpenAI / Azure / Apertus clients, model choice
  kb/
    services.yaml     20 service cards      playbook.jsonl   21 real resolution notes
    roster.yaml       people, roles, teams  sync.py / learn.py  load files / learn from done tickets
  scripts/            import tickets, build playbook/roster, sync, export contract, seed_demo
alembic/versions/     migrations (own version table: alembic_version_triage)
migrations_sql/       the same migrations as plain SQL for the Supabase SQL editor, snapshot, rollback
tests/                pytest (57 tests: domain, rubric, confidence, llm, ingest, chat, contract,
                      work + permissions, retrieval, intake + KPIs)
```

## Common tasks

```bash
make test                                   # backend tests + frontend lint/build
docker compose exec backend pytest -q       # backend tests only
make contract                               # after changing schemas.py or a route
make migration m="describe the change"      # after changing models.py
make seed-demo / make clear-demo            # simulated 4-week history
```

The backend runs `alembic upgrade head` and syncs the knowledge base and roster on every start.
Details: [Development workflow](../docs/wiki/12-Development-Workflow.md),
[API reference](../docs/wiki/09-API-Reference.md), [Configuration](../docs/wiki/11-Configuration.md).
