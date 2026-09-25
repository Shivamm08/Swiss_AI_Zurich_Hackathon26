# Frontend

React 19 + TypeScript + Vite + Tailwind CSS v4, TanStack Query for data, React Router for pages,
lucide icons. See the [root README](../README.md) for running everything and the
[frontend guide](../docs/wiki/10-Frontend-Guide.md) for the screens.

```
src/
  api/
    schema.d.ts     GENERATED from ../contracts/openapi.json. Never edit by hand (npm run gen:api)
    client.ts       typed fetch client (openapi-fetch)
    types.ts        friendly aliases for the generated types
    hooks.ts        one React Query hook per backend endpoint
    stream.ts       live triage walkthrough (server-sent events)
    copilot.ts      Copilot chat stream (sources, tokens, grounding)
  components/
    Layout.tsx      sidebar, top bar, role-based navigation and badges
    ui.tsx          UI primitives (Card, Button, Pill, WorkStatusPill…)
    triage.tsx      triage widgets: SLA timer, confidence, matrix, evidence, AI reads / Rule / Lookup tags with (i)
    fields.ts       how every field is produced (text behind the (i) buttons)
    Walkthrough.tsx the live triage walkthrough
    ComposeDialog   escalate / ask a question, drafted by the Copilot
    PersonaSwitcher "View as" anyone (no login in the demo)
    charts.tsx      hand-built SVG charts for the Impact dashboard
  copilot/          the Copilot panel and its state
  pages/            one file per screen (Queue, Ticket, New ticket, Messages, People, Team, Impact,
                    Knowledge base, Intake & export, Settings)
  viewas/           who you're viewing as; permission helpers (canDispatch, canManageTicket, canEscalateTicket)
  model/            the model picker state
```

Rule of thumb: pages call hooks, hooks call `api`, and nothing else calls `fetch` directly (the two
streams in `api/stream.ts` and `api/copilot.ts` are the exceptions). If the backend changes an
endpoint, `make contract` and the TypeScript compiler shows every place that must change.

The UI hides what a role can't do, and restricted pages are blocked by URL too, but the backend
enforces every permission itself.
