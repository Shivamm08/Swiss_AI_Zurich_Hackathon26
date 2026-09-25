# Swiss Life Triage Agent: Swiss {ai} Weeks Zurich 2026

An AI agent that triages Jira service-desk tickets the way an L2 analyst would.
It works out the real service, team, assignee, priority and resolution, then
drafts a resolution comment. A human analyst approves, edits or rejects each proposal.

```
ticket/email ─▶ retrieve (RAG) ─▶ classify (LLM) ─▶ rules (code) ─▶ draft (LLM) ─▶ analyst review ─▶ export
                 service cards     work type,        team = map        resolution     approve/edit/
                 + playbook        service, U/I,     priority = matrix comment        reject + metrics
                                   resolution        assignee = resolver
```

| Layer    | Stack |
|----------|-------|
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Database | PostgreSQL + pgvector (shared **Supabase**, or local Docker) |
| AI       | Azure OpenAI (chat + embeddings). Without keys the app runs in *heuristic mode* |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Router |
| Contract | OpenAPI → generated TypeScript types (`openapi-typescript` + `openapi-fetch`) |

---

## Quick start

Needs Docker Desktop. Node and Python are only needed if you run things outside Docker.

```bash
cp .env.example .env              # then fill in DATABASE_URL (Supabase) and Azure keys if you have them
# copy the challenge JSON file into data/raw/  (see data/README.md)

make up                           # shared Supabase DB from .env
# or
make up-local                     # throwaway local Postgres, no Supabase needed

make import-challenge             # in a second terminal: load the 20 challenge tickets
```

- App: http://localhost:5173
- API docs (Swagger, try every endpoint): http://localhost:8000/docs

On start the backend applies DB migrations and loads the knowledge base
(`backend/app/kb/`) automatically. Run `make help` for all commands.

### Supabase (shared team database)

1. One person creates the Supabase project and invites the others.
2. Project Settings → Database → **Connect** → copy the **Session pooler** URI
   (the direct connection is IPv6-only and usually fails from Docker).
3. Share it privately. Everyone puts it in their own `.env` as `DATABASE_URL`.
   **Never commit it. This repo is public.**
4. `make up`. The first start creates the tables and enables `pgvector`.

**Schema changes on the shared database.** The backend runs `alembic upgrade head` on every
start, so the first teammate who starts a newer version migrates Supabase for everyone.
Migrations are additive (new tables, nullable or defaulted columns), so teammates on older
code keep working. To apply one by hand instead, paste the matching file from
`backend/migrations_sql/` into the Supabase SQL Editor; it also bumps `alembic_version`, so
the automatic step then does nothing. Generate that file for a new migration with
`docker compose run --rm --no-deps backend alembic upgrade <from>:<to> --sql`.

On start the backend also loads `backend/app/kb/roster.yaml` into the `users` table. It's a
generated roster (the data has no real team membership); edit the YAML to change teams,
roles or capacity.

---

## Keeping frontend and backend compatible

The backend is the source of truth for the API. The frontend never hand-writes request or response types.

```
backend/app/schemas.py + routes ──▶ contracts/openapi.json ──▶ frontend/src/api/schema.d.ts
          (you edit)                 (generated, committed)       (generated, committed)
```

1. Change a Pydantic model in `backend/app/schemas.py` or a route in `backend/app/api/`.
2. Run **`make contract`**. It regenerates both files.
3. Run `npm run build` in `frontend/` (or `make test`). TypeScript now flags every
   frontend call that no longer matches.
4. Commit the code **and** both generated files in the same PR.

CI fails if a PR changes the API without regenerating the contract, or changes
`models.py` without a migration. Frontend work can start before an endpoint
exists: agree on the Pydantic model first, run `make contract`, then build
against the generated types while the backend implements it.

Frontend rules: pages use hooks from `src/api/hooks.ts`, hooks use the typed `api`
client, and nothing calls `fetch` directly. All routes are under `/api`, and Vite
proxies `/api` to the backend, so there's no CORS setup or hard-coded URLs.

---

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/health` | DB and LLM status |
| GET  | `/api/reference` | Enums, service catalogue, priority matrix (for dropdowns) |
| POST | `/api/reference/priority` | Urgency + Impact → Priority |
| GET  | `/api/tickets` | Queue (filter by `state`, `source`, `q`) |
| POST | `/api/tickets` | Create a ticket manually |
| POST | `/api/tickets/from-email` | Create a ticket from an email |
| POST | `/api/tickets/import` | Upload a Jira export JSON |
| GET / DELETE | `/api/tickets/{id}` | Ticket + latest proposal + review history |
| POST | `/api/tickets/{id}/triage` | Run the pipeline on one ticket |
| POST | `/api/triage/batch` | Triage all `new` tickets (or a list) |
| GET  | `/api/triage/{result_id}` | One proposal |
| POST | `/api/triage/{result_id}/review` | Analyst approve / edit / reject |
| GET  | `/api/kb/documents` | Knowledge base contents |
| POST | `/api/kb/search` | Retrieval test (hybrid BM25 + vector) |
| POST | `/api/kb/sync` | Reload KB files into the DB (+ embeddings) |
| POST | `/api/assistant/ask` | RAG Q&A with citations |
| GET  | `/api/metrics` | Acceptance rate, review time, most-corrected fields |
| GET  | `/api/export/submission` | Challenge-format JSON with our answers |

## Where things live

```
backend/app/
  domain.py        enums, service→team map, priority matrix (from the challenge README)
  schemas.py       API contract (request/response models)
  models.py        DB tables (+ alembic/versions for migrations)
  api/             routes
  pipeline/        retrieve.py, classify.py (LLM), rules.py (code), draft.py (LLM), pipeline.py
  kb/              services.yaml (service cards), playbook.jsonl (resolution playbook), sync.py
  scripts/         import_tickets, build_playbook, sync_kb, export_openapi
frontend/src/
  api/             generated types, typed client, hooks
  pages/           Dashboard, Ticket queue, Ticket detail + review, Knowledge base, Assistant, Import/export
contracts/         openapi.json (generated)
data/raw/          challenge files (git-ignored)
```

**Plugging in work**
- *Data / model work:* improve `kb/services.yaml`, `kb/playbook.jsonl`, the
  assignee fallback in `pipeline/rules.py`, and add an evaluation set.
- *AI:* prompts live in `pipeline/classify.py` and `pipeline/draft.py`.
- *Frontend:* `frontend/src/pages/*` are working starting points wired to every endpoint.

## Team conventions

- Branch from `main` and open a PR. Keep PRs small, and pull often.
- DB change: edit `models.py`, then `make migration m="what changed"`, then commit the migration.
  Pull before creating one so we don't end up with two parallel migrations.
- API change: run `make contract` and commit the generated files.
- Never commit `.env`, keys or `data/raw/*`.

## Running without Docker

```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head && python -m app.scripts.sync_kb
uvicorn app.main:app --reload            # reads ../.env

# frontend
cd frontend && npm install && npm run dev
```
