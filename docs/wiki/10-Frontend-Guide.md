# 10 · Frontend guide

Stack: React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query (data fetching), React Router,
lucide-react (icons). Code in `frontend/src/`.

## Screens

| Route | Screen | Who sees it | What's on it |
|---|---|---|---|
| `/` | **Queue** | everyone | Tabs by role. Analyst: Triage inbox · Needs review · My department · Escalations · All. Specialist: My work · My department · Escalations · All. Admin: Triage inbox (all departments) · Needs review · Escalations · All. Done tickets hidden unless **Show done** is ticked. Sorted by priority score, with SLA countdown, intake→AI service change, confidence, and a status pill (not triaged, needs review, awaiting analyst + confidence label, assigned, in progress, waiting for info, done). Untriaged rows have a **▶ Triage** button |
| `/tickets/:id` | **Ticket** | everyone | Header (status, specialist) · **Live triage walkthrough** · As received · Closing note (when done) · AI proposal · Why this priority (matrix) · Suggested resolution · Confidence · Specialist (suggestion + candidates with dispatch/reassign) · Evidence · Activity. Bottom bar by role: analyst **Approve & dispatch / Edit / Reject** while open; assigned specialist **Start / Waiting for info / Resume / Mark done** |
| `/new` | **New ticket** | analyst, admin | Required: summary, description, reporter. Optional "Set details yourself" for every AI-fillable field. Buttons: *Create and watch AI triage* / *Create only* |
| `/messages` | **Messages** | everyone | Department channels and direct messages; ticket cards; escalations |
| `/people` | **People & teams** | everyone | Department cards, members with load, message buttons |
| `/team` | **Team workload** | analyst, admin | Per-specialist load, share, done in 7 days, flags, escalations |
| `/dashboard` | **Impact** | analyst, admin | Pain points we solve, headline numbers, trends, calibration ([details](14-Impact-and-Demo-Data.md)) |
| `/knowledge` | **Knowledge base** | admin | Test retrieval; browse service cards, playbook, learned tickets; re-sync |
| `/intake` | **Intake & export** | admin | Import JSON, paste an email, **batch triage**, download `submission.json` |
| `/settings` | **Settings** | admin | Thresholds, SLA targets, matrix, roster (read-only) |

The **top bar** has the status dot, the **model** picker, the **Copilot** button (⌘K) and the
**persona button**, which opens the persona switcher (search, demo personas, everyone by department).
Persona and model are remembered per browser (`localStorage` keys `view-as` and `llm-model`).
The **Copilot** panel is available on every screen ([Collaboration and Copilot](13-Collaboration-and-Copilot.md)).
On a ticket, **Escalate** / **Message about this ticket** open the AI-drafted message dialog.

### The live walkthrough

Opening a ticket with `?run=1`, or clicking **Watch the AI triage it / Re-run live**, calls
`GET /api/tickets/{id}/triage/stream` and draws a timeline with six steps:
1. **Retrieve precedent:** the 6 documents with scores.
2. **Read the ticket:** three vote cards fill in as they arrive. Values that differ from the
   majority are highlighted amber, then the agreement per field (staff-set fields say so).
3. **Decide priority:** fact chips, the rule sentences, the matrix cell highlighted.
4. **Measure confidence:** each part, overall, route, escalation.
5. **Route to a person:** expert, working assignee, candidates with load.
6. **Draft the resolution.**

Each step shows its time. When "done" arrives, the page refreshes the proposal below.

## Visual language

Defined once as tokens in `src/index.css` (`@theme`), used as Tailwind classes:

| Token | Use |
|---|---|
| `canvas`, `surface`, `line`, `ink`, `muted` | Page background, cards, borders, text |
| `accent` (blue) | Primary actions, links, selection |
| `ai` (violet) | Anything the AI changed or produced (e.g. intake → **AI value**) |
| Priority colors | Highest red · High orange · Medium amber · Low sky · Lowest slate (`components/styles.ts`) |
| Confidence | green ≥ 80 · amber 50–79 · red < 50 |

Fonts: IBM Plex Sans (text) and IBM Plex Mono (IDs, scores).

## Code layout

```
src/
  api/
    schema.d.ts      GENERATED from contracts/openapi.json. Never edit by hand
    client.ts        typed fetch client (openapi-fetch) + unwrap()
    types.ts         friendly names for generated types (Ticket, TriageResult, …)
    hooks.ts         one React Query hook per endpoint (useTickets, useReviewTriage, …)
    stream.ts        useTriageStream(): reads the live triage events
    copilot.ts       useCopilotChat(): streams Copilot answers
  components/
    Layout.tsx       sidebar, top bar, role-based navigation
    ui.tsx           Card, PageHeader, Button, Pill, PriorityPill, StatePill, Field, EmptyState, …
    triage.tsx       ScoreBar, SlaTimer, ConfidenceMeter, RoutePill, FieldDiff, FactChips, MatrixGrid, EvidenceList
    Walkthrough.tsx  the live timeline
    charts.tsx       small SVG charts (line, stacked columns, bars) for the Impact screen
    people.tsx       Avatar, AvatarStack, LoadBar
    PersonaSwitcher.tsx, ComposeDialog.tsx
    styles.ts        priority colors, avatar colors, chart series colors
  copilot/           CopilotProvider (state, ⌘K), CopilotPanel (the chat UI)
  pages/             one file per screen
  viewas/            "View as" state (ViewerProvider, useViewer)
  model/             model picker state (ModelProvider, useSelectedModel)
```

**Rule:** pages call hooks, hooks call the typed `api` client, and nothing else calls `fetch`
directly (the one exception is `stream.ts`, because the client can't stream). All paths start with
`/api`; Vite proxies them to the backend, so there's no CORS setup and no hard-coded URLs.

## How to add something

**A new screen**
1. Create `src/pages/MyPage.tsx`; start with `<PageHeader title="…" subtitle="…" />` and `Card`s.
2. Add a `<Route>` in `src/App.tsx`.
3. Add it to `NAV` in `components/Layout.tsx` (with `roles` if it's restricted).

**Using a new backend endpoint**
1. The backend adds it and runs `make contract`.
2. Add a hook in `src/api/hooks.ts`, e.g.
   ```ts
   export const useThing = (id: string) =>
     useQuery({ queryKey: ['thing', id], queryFn: () => unwrap(api.GET('/api/thing/{id}', { params: { path: { id } } })) })
   ```
3. Use the hook in a page. TypeScript checks the path, parameters and response shape.

**Checks before committing:** `npm run lint` and `npm run build` in `frontend/` (or `make test`).
