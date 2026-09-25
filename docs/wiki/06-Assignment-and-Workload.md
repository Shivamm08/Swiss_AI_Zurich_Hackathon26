# 6 · Assignment and workload

Code: `backend/app/pipeline/assignment.py`, `backend/app/pipeline/rules.py`.

## Two assignees, on purpose

| | Expert | Recommended |
|---|---|---|
| Who | The person who wrote the matched past solution (playbook entry or approved ticket) | The best team member once workload is considered |
| Stored in | The proposal (`triage_results.assignee`) | The ticket (`tickets.assignee`, the working assignee) |
| Used for | The **challenge export** (the "person implied by the content") | The live queues ("My queue") |

Usually they're the same person. They differ when the expert is overloaded.

### Where the expert comes from

In the training data the `Assignee` column is random. But each of the **21 detailed resolution
notes was always written by the same person**. Example: Trade Matching fixes are always by
quinn.anderson, and Client Reporting fixes always by pierre.johnson. That author is the expert.
Approved tickets in the app also record who resolved them, so they become experts too.

For services with no resolution notes, there is no expert yet (until tickets get approved). The
recommendation then falls back to workload balancing within the team.

## The recommendation formula

Candidates are the members of the team that owns the service (from the roster, admins excluded).

```
open(p)         = tickets assigned to p that are proposed / approved / edited, and not closed (status ≠ done)
expertise(p)    = 1.0 if p is the expert
                  + 0.5 × min(1, approved tickets p handled on this service / 5)      (capped at 1)
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

**Who ends up working on it:**
- If the route is `auto` or `review`, the recommended person.
- If the route is `triage`, nobody yet: a team lead assigns it from Needs review.
- If staff chose an assignee when creating the ticket, that person, always.

Anyone can reassign from the ticket screen (`POST /api/tickets/{id}/assign`). Assigning a
Needs-review ticket moves it to `review`.

## The roster

The data has no real team membership (all 30 assignees appear in every team), so
`backend/app/kb/roster.yaml` holds a **generated, plausible roster**:

- **35 people:** the 30 assignee names, plus the playbook authors, plus one admin (`admin@intcom.com`).
- Every playbook author is placed in the team that owns their services. One person can be in
  two teams (e.g. xena.schmidt: Enterprise Applications and Securities Operations).
- Everyone else is spread so each team has 3–4 people.
- The first non-author member of each team is its **lead**. Capacity is 8 for everyone.

The backend loads it into the `users` table on every start (it upserts, so people added directly
in the database stay). To change teams, roles or capacity, edit the YAML and restart. To
regenerate it from the data:

```bash
docker compose exec backend python -m app.scripts.build_roster /data/jira_first_20000_requested_fields_synthetic.json
```

## Team workload screen

`GET /api/workload?team=…` returns, per member: open tickets vs capacity, share of the team's
open tickets, open High/Highest tickets, the oldest open ticket, and approvals in the last 7 days,
plus the team's open escalations. The screen flags anyone at or over capacity or holding
30% or more of the team's tickets.
