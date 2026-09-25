# 6 · Assignment and workload

Code: `backend/app/pipeline/assignment.py`, `backend/app/pipeline/rules.py`.

## Two assignees, on purpose

| | Expert | Recommended |
|---|---|---|
| Who | The person who wrote the matched past solution (playbook entry or a done ticket) | The best **specialist** in the team once workload is considered |
| Stored in | The proposal (`triage_results.assignee`) | The proposal's suggestion; becomes `tickets.assignee` when the analyst approves |
| Used for | The **challenge export** (the "person implied by the content") | The analyst's one-click dispatch ("My work" for the specialist) |

Usually they're the same person. They differ when the expert is overloaded.

### Where the expert comes from

In the training data the `Assignee` column is random. But each of the **21 detailed resolution
notes was always written by the same person**. Example: Trade Matching fixes are always by
quinn.anderson, and Client Reporting fixes always by pierre.johnson. That author is the expert.
Tickets marked done in the app record who resolved them, so those specialists become experts too.

For services with no resolution notes, there is no expert yet (until tickets are done). The
recommendation then falls back to workload balancing within the team.

## The recommendation formula

Candidates are the **specialists** of the team that owns the service (from the roster). Analysts
(team leads) and the admin dispatch work but never hold tickets.

```
open(p)         = tickets with p whose work status is assigned, in progress or waiting
expertise(p)    = 1.0 if p is the expert
                  + 0.5 × min(1, tickets p marked done on this service / 5)          (capped at 1)
availability(p) = 1 − open(p) / capacity(p)                     capacity default: 8
score(p)        = 0.6 × expertise(p) + 0.4 × availability(p)
```

A person is **skipped** if:
- they are at or over capacity, or
- the team has real volume (at least **2 open tickets per member**) and they already hold
  **30% or more** of them. Below that volume the share rule is off: in a 3-person team, holding
  1 of 3 tickets is already 33%, which is just a fair share.

The highest-scoring person who isn't skipped is recommended. If everyone is skipped, the best
score wins anyway. The screen shows the reason, e.g.
*"expert over capacity (9/8): next best team member"*.

**Who ends up working on it:** nobody, until the department's Team Lead / Analyst decides.
- **Approve:** the recommended specialist (or the staff-chosen assignee, if one was set).
- **Edit:** the specialist they picked; if they moved the ticket to another team, a fresh
  recommendation for that team.
- **Needs review** (low confidence or rejected): an analyst dispatches it from the candidate list.

Analysts and the admin can dispatch or reassign from the ticket screen
(`POST /api/tickets/{id}/assign`) until the ticket is done. See
[Roles and ticket lifecycle](15-Roles-and-Ticket-Lifecycle.md).

## The roster

The data has no real team membership (all 30 assignees appear in every team), so
`backend/app/kb/roster.yaml` holds a **generated, plausible roster**:

- **35 people:** the 30 assignee names, plus the playbook authors, plus one admin (`admin@intcom.com`).
- Every playbook author is placed in the team that owns their services. One person can be in
  two teams (e.g. xena.schmidt: Enterprise Applications and Securities Operations).
- Everyone else is spread so each team has 3–4 people.
- The first non-author member of each team is its **Team Lead / Analyst** (role `analyst`); everyone
  else is a **specialist**. No playbook author is an analyst, so every expert can take work.
  Capacity is 8 for everyone. Result: 11 analysts, 23 specialists, 1 admin.

The backend loads it into the `users` table on every start (it upserts, so people added directly
in the database stay). To change teams, roles or capacity, edit the YAML and restart. To
regenerate it from the data:

```bash
docker compose exec backend python -m app.scripts.build_roster /data/jira_first_20000_requested_fields_synthetic.json
```

## Team workload screen

`GET /api/workload?team=…` returns, per specialist: open tickets vs capacity, share of the team's
open tickets, open High/Highest tickets, the oldest open ticket, and tickets done in the last 7 days,
plus the team's open escalations. The screen flags anyone at or over capacity or holding
30% or more of the team's tickets.
