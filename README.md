# ![Triage Copilot](https://swiss-ai-zurich-hackathon26.vercel.app/)

**An AI copilot for IT service desks, with humans in charge.** Built for the Swiss Life challenge
*"AI Support Agent for Operational Service Desks"* at Swiss {ai} Weeks, Zurich 2026.

A Jira ticket arrives. Triage Copilot works out what it really is (incident or request), which
service and team own it, how urgent it is, who should handle it and how it will probably be
resolved, and shows every step. The department's **Team Lead / Analyst** approves the proposal,
a **Specialist** does the work and closes it, and only then does the fix become knowledge for the
next similar ticket.

![The queue: every open ticket ranked by priority, with SLA timers, AI confidence and status](docs/images/queue.png)

---

## Why it exists

| Service-desk pain | What Triage Copilot does |
|---|---|
| Tickets bounce between teams | The AI reads the content, not the (often wrong) intake field, and re-routes with visible reasons |
| "Everything is urgent" | Priority comes from fixed rules and the official Urgency × Impact matrix. No AI chooses a priority |
| Fixes live in people's heads | Every finished ticket, with the specialist's own closing note, becomes searchable knowledge |
| Tickets wait hours for triage | A full proposal in 3–6 seconds, with an SLA timer from arrival |
| One expert gets everything | The suggested specialist balances expertise with workload and capacity |
| Escalations get lost in email | Escalate one level up with an AI-drafted message attached to the ticket |
| Nobody trusts a black-box AI | Every step is shown live, confidence is measured, and a human approves every ticket |
| "pls fix asap" tickets | Vague tickets are flagged and the draft asks for what's missing; nonsense is rejected at the door |

---

## See it in action

### 1. Watch the AI triage a ticket, live

Every stage streams to the screen as it happens: knowledge found, three independent AI readings
side by side, the priority rules and matrix cell, the confidence, the suggested specialist, and the
draft.

![Live triage walkthrough](docs/images/walkthrough.png)

### 2. Every field says how it was produced

**AI reads** (from the text, 3 votes, fixed options only), **Rule** (computed, never guessed) or
**Lookup** (fixed table). The (i) explains the exact calculation. Staff-set values are kept but
cross-checked; disagreements are flagged for the analyst.

![Ticket screen with method tags and an (i) explanation](docs/images/ticket.png)

### 3. The analyst decides, one click

Every ticket waits for its department's Team Lead / Analyst, however confident the AI is. Approve
dispatches it to the suggested specialist; the confirmation offers the next ticket in the inbox.

| Decide | Dispatched |
|---|---|
| ![Decision bar](docs/images/decision-bar.png) | ![Dispatched confirmation](docs/images/decision-done.png) |

### 4. The specialist works it and closes it

**My work** shows the specialist's tickets. They start, wait for information, hand back (with a
reason) or **mark done** with the real closing note, which is what the knowledge base learns from.

| My work | Mark done |
|---|---|
| ![Specialist queue](docs/images/my-work.png) | ![Mark done with a closing note](docs/images/mark-done.png) |

### 5. The analyst is told, and can reopen

When a ticket is done, the Team Lead / Analyst gets a message with the resolution. Not satisfied?
**Reopen** sends it back to the specialist and takes the fix out of the knowledge base.

![Ticket-done notification in Messages](docs/images/messages.png)

### 6. The Copilot answers from team knowledge, and refuses the rest

A chat assistant on every screen (⌘K). It answers only from relevant knowledge, cites each source
with its similarity, says so when nothing matches, and declines questions that aren't about
service-desk work.

![Copilot with cited sources and an off-topic refusal](docs/images/copilot.png)

### 7. Escalate one level up

Specialist → their Team Lead / Analyst → the Admin. The Copilot drafts the message with the
ticket's context; the ticket is flagged until the analyst de-escalates it.

![Escalate dialog](docs/images/escalate.png)

### 8. New tickets, checked at the door

Analysts and the admin create tickets. Anything they set is kept and double-checked. Text that
isn't a ticket at all is rejected with a reason; vague but real tickets are accepted.

| New ticket | Nonsense rejected |
|---|---|
| ![New ticket form with method tags](docs/images/new-ticket.png) | ![A nonsense ticket rejected](docs/images/new-ticket-rejected.png) |

### 9. People, personas and workload

| People & teams | View as anyone | Team workload |
|---|---|---|
| ![People and teams](docs/images/people.png) | ![Persona switcher](docs/images/persona.png) | ![Team workload](docs/images/team.png) |

### 10. Impact and desk KPIs

Time to assign, first-time accuracy (per field), AI misroutes, reassignments and reopens, next to
the pain points and trends. The four-week history behind the trends is simulated and labelled.

| KPIs and pain points | Trends |
|---|---|
| ![Impact dashboard](docs/images/impact.png) | ![Impact trends](docs/images/impact-trends.png) |

### 11. Admin: knowledge base and the challenge set

| Knowledge base | Challenge set statistics |
|---|---|
| ![Knowledge base](docs/images/knowledge.png) | ![Challenge statistics](docs/images/challenge.png) |

<p align="center"><img src="docs/images/mobile.png" width="280" alt="The queue on a phone"><br><sub>Works on a phone too.</sub></p>

More screens and details: **[Screen tour](docs/wiki/16-Screen-Tour.md)**.

---

## How it works

```mermaid
flowchart LR
  A[Ticket, email<br/>or New ticket] --> I{Intake check}
  I -->|not a ticket| X[Rejected with a reason]
  I --> B[Find relevant<br/>past fixes]
  B --> C[AI reads the ticket<br/>3 independent votes]
  C --> D[Rules decide<br/>priority]
  D --> E[Confidence<br/>+ SLA]
  E --> F[Suggest a<br/>specialist]
  F --> G[Draft the<br/>resolution]
  G --> H[Team Lead / Analyst<br/>approves, edits or rejects]
  H -->|dispatch| S[Specialist works it:<br/>in progress, waiting]
  S -->|done + closing note| KB[(Knowledge base)]
  KB --> B
  S -->|hand back| H
  KB -. reopen .-> S
```

**The one design rule:** the AI reads and judges; plain code decides anything that can be looked up
or calculated.

| The AI reads | Rules and lookups compute |
|---|---|
| Work type, service, resolution status, and five facts (who's affected, how broken, workaround, regulatory breach, deadline) | Team (lookup), impact and urgency (rubric), priority (official matrix), 0–1 ranking score, confidence, route, SLA, escalation, the suggested specialist |

**What stops the AI from hallucinating:** fixed answer options only; three independent readings
whose disagreement lowers confidence; a matched fix must be one that was actually retrieved and
belong to the chosen service; only documents at least 40% similar are ever shown to the AI; with no
precedent the draft is "first steps", never an invented resolution; staff values are cross-checked;
the Copilot refuses off-topic questions and never cites a source it wasn't given; an analyst approves
every ticket; only a specialist's real closing note enters the knowledge base.

### Three roles

| Role | Does |
|---|---|
| **Team Lead / Analyst** (one per department) | Checks every AI proposal, dispatches it, reassigns, handles escalations, reopens unsatisfying fixes, creates tickets |
| **Specialist** | Starts, waits for info, hands back, marks done with the closing note, escalates |
| **Admin** | Knowledge base, intake and export, settings; can act on any ticket |

Lifecycle: *awaiting analyst → assigned → in progress / waiting for info → done*. The backend
enforces who may do what; details in [Roles and ticket lifecycle](docs/wiki/15-Roles-and-Ticket-Lifecycle.md).

---

## Quick start (local, about 5 minutes)

**You need:** Docker Desktop (running), `git`, `make`, and ideally an OpenAI API key.

```bash
git clone https://github.com/Shivamm08/Swiss_AI_Zurich_Hackathon26.git
cd Swiss_AI_Zurich_Hackathon26

cp .env.example .env          # then open .env and paste your OPENAI_API_KEY
# put the challenge file into data/raw/ (see data/README.md)

make up-local                 # start everything with a local database (keep this terminal open)
```

In a **second terminal**, once the logs show `Application startup complete`:

```bash
make import-challenge         # load the 20 challenge tickets (once)
make seed-demo                # optional: a clearly labelled, simulated 4-week history for demos
```

Open **http://localhost:5173**. Click **▶ Triage** on any ticket to watch the AI work through it
live, press **⌘K / Ctrl+K** for the Copilot, and use the persona button (top right) to see the app
as a Team Lead / Analyst, a Specialist or the Admin.

| Address | What |
|---|---|
| http://localhost:5173 | The app |
| http://localhost:8000/docs | API documentation (try every endpoint) |

**Deploying?** Backend on Render (`render.yaml`, root directory `backend`), frontend on Vercel (root directory
`frontend`, `VITE_API_URL` = the Render URL): see [Deploying](docs/wiki/02-Setup-and-Running.md#deploying-vercel--render).

No OpenAI key? The app still runs in **heuristic mode**: it keeps the intake values and marks
everything low-confidence. Stop the app with `Ctrl+C` or `make down`.

---

## Documentation

The full guide is the **[project wiki](docs/wiki/Home.md)**:

| Page | Read it when you want to… |
|---|---|
| [What and why](docs/wiki/01-What-and-Why.md) | understand the challenge, the product and the key terms |
| [Setup and running](docs/wiki/02-Setup-and-Running.md) | install, run, switch databases, fix common problems |
| [Architecture](docs/wiki/03-Architecture.md) | see how the pieces fit together |
| [Triage pipeline](docs/wiki/04-Triage-Pipeline.md) | follow one ticket through every step, and see which fields use the AI |
| [Priority and confidence](docs/wiki/05-Priority-and-Confidence.md) | know exactly how priority, confidence and routing are decided |
| [Assignment and workload](docs/wiki/06-Assignment-and-Workload.md) | know who gets a ticket and why |
| [Knowledge base and RAG](docs/wiki/07-Knowledge-Base-and-RAG.md) | understand retrieval, relevance and the learning loop |
| [Data and database](docs/wiki/08-Data-and-Database.md) | learn the dataset facts, tables and migrations |
| [API reference](docs/wiki/09-API-Reference.md) | call the backend |
| [Frontend guide](docs/wiki/10-Frontend-Guide.md) | work on the UI |
| [Configuration](docs/wiki/11-Configuration.md) | change settings in `.env` |
| [Development workflow](docs/wiki/12-Development-Workflow.md) | contribute without breaking things |
| [Collaboration and Copilot](docs/wiki/13-Collaboration-and-Copilot.md) | use the Copilot, messages, escalations and personas |
| [Impact and demo data](docs/wiki/14-Impact-and-Demo-Data.md) | see the KPIs, the pain points and how the demo history is made |
| [Roles and ticket lifecycle](docs/wiki/15-Roles-and-Ticket-Lifecycle.md) | know who does what, from arrival to done |
| [Screen tour](docs/wiki/16-Screen-Tour.md) | walk through every screen with screenshots |

Also: [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md), [data/README.md](data/README.md).

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| AI | OpenAI (default) or Azure OpenAI, chosen per request in the UI. Embeddings: `text-embedding-3-small` |
| Database | PostgreSQL 16/17 + pgvector: local in Docker, or the shared Supabase project |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Router, lucide icons |
| Contract | OpenAPI → generated TypeScript types, so frontend and backend can't drift apart |
| Tooling | Docker Compose, Makefile, GitHub Actions CI, 57 backend tests |

## Everyday commands

| Command | What it does |
|---|---|
| `make up-local` | Start everything with a **local** database |
| `make up` | Start everything against `DATABASE_URL` in `.env` (**shared Supabase**) |
| `make down` | Stop everything (data is kept) |
| `make import-challenge` | Load the 20 challenge tickets (once per database) |
| `make seed-demo` / `make clear-demo` | Add / remove the simulated 4-week demo history |
| `make test` | Backend tests + frontend lint and build |
| `make contract` | Regenerate API types after changing the backend API |
| `make logs` | Follow the backend logs |
| `make help` | List all commands |

## Repository layout

```
backend/        FastAPI app, triage pipeline, knowledge base files, migrations, tests
frontend/       React app (screens, Copilot, API client generated from the contract)
contracts/      openapi.json: the API contract, generated from the backend
data/           training data, the team's data-science experiments (challenge file goes in data/raw/)
docs/wiki/      the project wiki
docs/images/    screenshots
PRESENTATION_SCRIPT.md, PowerPointDescription, *.svg   pitch script and slide material
```

## Team rules (short version)

1. **Never commit secrets.** Keys live only in `.env`, and this repo is public.
2. **Changed the API?** Run `make contract` and commit the generated files.
3. **Changed `models.py`?** Create a migration, and push it **before** applying it to Supabase.
4. **Never tune prompts or models on the 20 challenge tickets.** The challenge forbids it.
5. Work on a branch and open a pull request. Never force-push shared branches.

Details: [Development workflow](docs/wiki/12-Development-Workflow.md).
