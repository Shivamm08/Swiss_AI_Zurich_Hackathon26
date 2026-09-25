# 12 · Development workflow

## Git

- `main` holds the integrated code. Work happens on branches (currently **`triage-copilot`**).
- One feature per branch, then a pull request. Pull often.
- **Never force-push** a shared branch.
- Before every commit, check that no secret is staged:
  ```bash
  git status                                            # .env must not appear
  git diff --cached | grep -cE "sk-[A-Za-z0-9_-]{20,}"   # must print 0
  ```
- Don't commit generated or bulky files: `.idea/`, `data/output/`, large CSVs, `node_modules/`.

## The contract (keeping frontend and backend in sync)

After **any** change to `backend/app/schemas.py` or a route:

```bash
make contract     # regenerates contracts/openapi.json and frontend/src/api/schema.d.ts
```

Commit both generated files with your change. The frontend's TypeScript build then shows every
place that needs updating. CI fails if the generated files are stale (`tests/test_contract.py`
and a diff check).

## Tests and checks

```bash
make test         # backend pytest + frontend lint and build
```

| Test file | Checks |
|---|---|
| `test_domain.py` | Matrix cells match the README; every service has a team; level normalisation |
| `test_rubric.py` | All 360 fact combinations × services × work types give a consistent verdict; score stays in its band; age never crosses a band; example rules |
| `test_confidence.py` | Weakest-part rule, flags, heuristic, retrieval rescaling, routes, SLA, vote majority |
| `test_llm.py` | Model choice, default model, validation, Apertus routing |
| `test_ingest.py` | Jira record → ticket mapping |
| `test_chat.py` | Channel ids and validation |
| `test_contract.py` | `contracts/openapi.json` is up to date |

## Database changes

See [Data and database → Migrations](08-Data-and-Database.md#migrations). In short: edit
`models.py`, then generate the migration against your **local** database, add its SQL twin,
commit, push, and only then apply it to Supabase.

## CI (GitHub Actions)

On every push to `main` and every pull request (`.github/workflows/ci.yml`):
- **Backend:** install, `pytest`, then `alembic upgrade head` + `alembic check` on a fresh Postgres
  (fails if `models.py` changed without a migration).
- **Frontend:** `npm ci`, regenerate API types and fail on diff, `lint`, `build`.

## Challenge rules we follow

- **Never tune prompts, thresholds or models on the 20 challenge tickets.** Use an evaluation set
  (training tickets rewritten into challenge style, tickets generated from the playbook, and
  hand-labelled examples). Run the challenge file once at the end.
- The export (`/api/export/submission`) uses the specialist's resolution and closing note for done tickets, the analyst's final decision where one exists, else
  the latest proposal. Its assignee is the **expert**.

## Typical tasks

| Task | Where |
|---|---|
| Improve service accuracy | `kb/services.yaml` boundaries; the extraction prompt in `pipeline/classify.py` |
| Change how priority is decided | `pipeline/rubric.py` (+ tests in `test_rubric.py`) |
| Change confidence or routing | `pipeline/confidence.py`, thresholds in `.env` |
| Change who gets tickets | `pipeline/assignment.py`, `kb/roster.yaml` |
| Change the resolution text style | `pipeline/draft.py` |
| Add a screen | [Frontend guide](10-Frontend-Guide.md#how-to-add-something) |
| Add an API field | `schemas.py` → route → `make contract` → frontend |
| Change the Copilot's behaviour | `COPILOT_PROMPT` in `api/knowledge.py` |
| Change drafted escalation messages | `DRAFT_PROMPT` in `api/chat.py` |
| Change the simulated history | `scripts/seed_demo.py`, then `make seed-demo` |
