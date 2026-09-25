# 2 · Setup and running

## Prerequisites

| Tool | Why | Check |
|---|---|---|
| **Docker Desktop**, running | Runs the database, backend and frontend | `docker info` prints a version |
| **git** | Get the code | `git --version` |
| **make** | Short commands | `make --version`. macOS: `xcode-select --install` if missing. Windows: use WSL2, or the raw commands below |
| **OpenAI API key** (recommended) | The AI steps | Without it the app runs in heuristic mode |
| Free ports **5173, 8000, 54322** | Frontend, backend, local database | Stop anything else using them |

You don't need Python or Node on your machine: everything runs inside Docker.

## First-time setup

```bash
git clone https://github.com/Shivamm08/Swiss_AI_Zurich_Hackathon26.git
cd Swiss_AI_Zurich_Hackathon26
git switch triage-copilot

cp .env.example .env
```

Open `.env` and set at least:

```
OPENAI_API_KEY=sk-...                                        # your key; never put it in .env.example
LLM_MODEL_CHOICES=gpt-5.4-mini,gpt-5.5,gpt-6-sol,gpt-4.1-mini   # models shown in the picker
```

Copy the challenge file (it's not in git) into `data/raw/`:

```
data/raw/jira_hackathon_blind_eval_challenge_20260923083915-1141.json
```

The training file `data/jira_first_20000_requested_fields_synthetic.json` is already in the repo.

## Start, use, stop

```bash
make up-local            # terminal 1: builds and starts everything (first build takes a few minutes)
make import-challenge    # terminal 2: once, after "Application startup complete"
```

Open http://localhost:5173.

Optional, for demos: `make seed-demo` adds a clearly labelled **simulated four-week history** so the
Impact dashboard, workload and messages look like a real desk (`make clear-demo` removes it). See
[Impact and demo data](14-Impact-and-Demo-Data.md).

What happens on start:
1. The **local Postgres** container starts (with the `pgvector` extension).
2. The **backend** applies database migrations, loads the knowledge base (service cards +
   playbook, creating embeddings if a key is set) and the roster, then serves the API on port 8000.
3. The **frontend** dev server starts on port 5173 and forwards `/api/*` to the backend.

| I want to… | Command |
|---|---|
| Start again next time | `make up-local` (your data is kept) |
| Stop | `Ctrl+C` in terminal 1, or `make down` |
| Wipe the local database and start fresh | `docker compose --profile local-db down -v`, then `make up-local` and `make import-challenge` |
| See backend logs | `make logs` |

Without `make` (e.g. Windows without WSL), run:

```bash
# macOS/Linux shell
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/triage docker compose --profile local-db up --build --renew-anon-volumes
# another terminal
docker compose exec backend sh -c 'python -m app.scripts.import_tickets /data/raw/jira_hackathon_blind_eval_challenge_*.json --source challenge'
```

## Local database vs shared Supabase

| | Local (`make up-local`) | Supabase (`make up`) |
|---|---|---|
| Where the data lives | A Docker volume on your laptop | The team's shared Supabase project |
| Who sees it | Only you | Everyone |
| Needs | Nothing extra | `DATABASE_URL` in `.env` (the **Session pooler** URI) |
| Start with | `make up-local` | `make up`, or plain `docker compose up --build` |
| Good for | Development and experiments | The shared demo data |

Supabase details:
- Use the **Session pooler** URI (Supabase → Connect → Session pooler). The direct connection is
  IPv6-only and usually fails from Docker. Encode special characters in the password (`@` → `%40`).
- The backend **applies pending migrations on start**, so starting a newer version changes the
  shared schema for everyone. Read [Data and database → Migrations](08-Data-and-Database.md#migrations) first.
- Run `make import-challenge` **once for the whole team**. Running it again duplicates the tickets.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `service "backend" is not running` on `make import-challenge` | The app isn't started | Run `make up-local` first and wait for `Application startup complete` |
| Backend exits with `Can't locate revision identified by '000X'` | The database has one of *our* migrations your code doesn't have yet | Pull the latest `triage-copilot`; see [Migrations](08-Data-and-Database.md#migrations) |
| Frontend shows `Failed to resolve import "lucide-react"` (or another package) | Old `node_modules` in the container after a dependency change | `make down` then `make up` / `make up-local` (they refresh dependencies). With plain docker: `docker compose up --build --renew-anon-volumes` |
| Top bar says **Heuristic mode** | No model configured | Set `OPENAI_API_KEY` in `.env`, then `make down && make up-local` |
| `Bind for 0.0.0.0:5173 failed: port is already allocated` | Another app uses the port | Stop it, or stop an older copy of this stack (`docker ps`) |
| Model picker lists 50+ models | `LLM_MODEL_CHOICES` missing in your `.env` | Add the line and restart |
| `password authentication failed` (Supabase) | Wrong or unencoded password | Check the URI; encode special characters |
| Backend fails with `set: Illegal option -` (Windows) | Script checked out with Windows line endings | The repo's `.gitattributes` prevents it; re-clone, or run `git add --renormalize .` |
| Changes to `.env` have no effect | Containers read `.env` only when created | `make down && make up-local` (not just a restart) |
