# 11 · Configuration

All settings come from **`.env`** in the repo root (copy `.env.example`). The code is
`backend/app/config.py`. Empty values fall back to the defaults. Containers read `.env` only when
they're created, so after a change run `make down` then `make up-local` (or `make up`).

**`.env` holds secrets and is git-ignored. Never put a real value in `.env.example`: the repo is public.**

## Database

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | local Postgres | Shared Supabase: the **Session pooler** URI. `postgres://` and `postgresql://` are both accepted. `make up-local` overrides it with the local database |

## LLM providers

The app uses **Azure OpenAI** if configured, else **OpenAI**, else heuristic mode.

| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | – | Secret. Enables the AI steps and embeddings |
| `OPENAI_CHAT_MODEL` | – | Default chat model. If empty, the first entry of `LLM_MODEL_CHOICES` is used |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embeddings are requested at 1,536 dimensions to match the database column |
| `LLM_MODEL_CHOICES` | – | Comma-separated models shown in the picker, e.g. `gpt-5.4-mini,gpt-5.5,gpt-6-sol,gpt-4.1-mini`. If empty, the picker lists every chat model your key can use |
| `LLM_TEMPERATURE` | – (model default) | Leave empty; some reasoning models reject other values |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` | – | Switch to Azure OpenAI (e.g. Swiss Life's) |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` | |
| `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | – | Azure uses deployment names instead of model ids |
| `APERTUS_API_KEY` | – | Optional: adds Swisscom's Apertus 1.5 70B to the picker. We dropped it from the main pipeline (rate limits, slow structured output). Keys from https://keymaker.ai-weeks.ch/ |
| `APERTUS_BASE_URL`, `APERTUS_MODEL` | hackathon product | Only change if Swisscom gives you different values |

## Triage policy

| Variable | Default | Meaning |
|---|---|---|
| `LLM_VOTES` | `3` | Independent extraction votes per ticket |
| `AUTO_THRESHOLD` | `0.80` | Confidence at or above this → route `auto` |
| `TRIAGE_THRESHOLD` | `0.50` | Confidence below this → route `triage` (Needs review) |
| `DEFAULT_CAPACITY` | `8` | Open tickets per person (roster value wins if set) |
| `MAX_SHARE` | `0.30` | Nobody is recommended once they hold this share of the team's open tickets (only when the team has 2+ open tickets per member) |
| `MANUAL_TRIAGE_MINUTES` | `8` | Assumed manual triage time per ticket, used for "analyst time saved" on the Impact screen |

SLA hours are in code (`pipeline/confidence.py`, `SLA_HOURS`).

## Other

| Variable | Default | Notes |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173` | Only needed if the frontend runs somewhere other than the Vite proxy |

## Files that act as configuration

| File | Edit it to… |
|---|---|
| `backend/app/kb/services.yaml` | Improve service descriptions and boundaries (biggest lever for service accuracy) |
| `backend/app/kb/roster.yaml` | Change teams, roles, capacity |
| `backend/app/kb/playbook.jsonl` | Add or refine resolution patterns (or regenerate with `make build-playbook`) |
| `backend/app/domain.py` | Services, teams, criticality, the priority matrix (fixed by the challenge) |

After editing a knowledge file, restart the backend or click **Re-sync from files** in the
Knowledge base screen.
