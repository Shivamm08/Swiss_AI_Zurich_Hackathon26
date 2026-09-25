# 14 · Impact dashboard and demo data

## Why this screen exists

The jury is business people. They don't need to see an API; they need to see **which everyday
problems of a Jira service desk disappear**. The Impact screen (Manage → Impact, analysts and admin)
is built around those problems.

## Pain points and the numbers behind them

| Pain point | What the system does | Number on the card | Computed from |
|---|---|---|---|
| "Tickets bounce between teams" | Reads the content, not the intake field; re-routes with reasons | **misrouted tickets caught** | latest proposals whose service ≠ intake service |
| "Everything is marked urgent" | Priority from an auditable rule and the matrix | **priorities corrected** | proposals whose priority ≠ submitted priority |
| "Fixes live in people's heads" | Every ticket marked done becomes knowledge (learning loop) | **resolved fixes now reusable** | `historical_ticket` documents in the knowledge base (real ones only) |
| "Tickets wait hours for first triage" | Full proposal in seconds, SLA timers | **seconds to a proposal** | average `latency_ms` of proposals |
| "One expert gets all the tickets" | Expertise balanced with capacity | **busiest person's load** + people over capacity | open tickets ÷ capacity per person |
| "Escalations get lost in email" | Automatic + AI-drafted escalations with the ticket attached | **escalations with full context** | tickets with `escalated = true` |
| "Nobody trusts a black-box AI" | Live walkthrough, measured confidence, an analyst approves every ticket | **high confidence: one-click approval** | share of proposals with route `auto` |
| "Vague tickets: pls fix asap" | Detected; the draft asks for what's missing | **vague tickets caught early** | proposals with resolution `clarification` |

Above them, three headline numbers: **analyst time saved**, **drafts accepted as proposed** and
**time to a full proposal**. Below them are the trends: tickets per day by route, a calibration
chart ("does confidence mean something?"), the acceptance rate and review time (7-day rolling),
open tickets per department, and the fields analysts correct most.

**Time saved** = tickets triaged × `MANUAL_TRIAGE_MINUTES` (default 8, an **assumption**) − the time
analysts actually spent reviewing. The card states it's an assumption; change it in `.env`.

API: `GET /api/metrics/impact?include_demo=true&days=28`.

## Desk KPIs

A row of KPIs above the pain points, computed from the activity timeline and the analysts'
decisions (`desk_kpis` in `backend/app/api/insights.py`, tested):

| KPI | Definition | Lower or higher is better |
|---|---|---|
| **Time to assign** | Median minutes from a ticket arriving to its dispatch to a specialist | lower |
| **First-time accuracy** | Analyst decisions that accepted the AI proposal with no field changed (`reviews.overridden_fields` empty) | higher |
| Kept as proposed, per field | For each field, the share of decisions where the analyst kept the AI's value | higher |
| **AI misroutes** | Decisions where the analyst changed the service (wrong department) or rejected the proposal | lower |
| **Reassigned** | Dispatched tickets later reassigned, or handed back by the specialist | lower |
| **Reopened** | Finished tickets the analyst reopened | lower |

"Misrouted tickets caught" (a pain-point card) is different: tickets whose **intake** service was
wrong and the AI corrected.

## The challenge set

Intake & export shows how the 20 challenge tickets are handled (`GET /api/metrics/challenge`):
triaged, average confidence, vote agreement, how many matched a past fix, routes, priority raised or
lowered versus intake, fields changed versus intake, and speed. The answer set is hidden, so these
are coverage and certainty figures, **not accuracy**. Never tune on these tickets.

## The simulated history (demo data)

Twenty challenge tickets can't show a trend. For the demo there's a **simulated four-week desk
history**. It's always labelled as simulated, and the dashboard has an **"Include simulated
4-week history"** switch. Untick it to see only real tickets.

```bash
make seed-demo     # create or re-create it (about 250 tickets, 200+ reviews, 120+ messages)
make clear-demo    # remove it; real tickets and messages are never touched
```

How it's generated (`backend/app/scripts/seed_demo.py`, fixed random seed, so every run is identical):

| Part | How |
|---|---|
| Tickets | From the training set's templates, 6–14 per weekday and 2–5 per weekend day, over 28 days. `source = "demo"` |
| Wrong intake | ~22% get a wrong intake service (a sibling service or the generic email bucket) |
| Facts → priority | Facts come from the template; the **real rubric** computes impact, urgency, priority and score. Severe events (full outage, regulatory breach) only occur on clear incident types |
| Confidence and routing | Confidence depends on how clear the template is; routing uses the **real thresholds** |
| Assignment | Expert if not clearly busier than the least-loaded teammate, like the real rule |
| Analyst decisions | Every ticket older than a day was decided by its department's Team Lead / Analyst (about half of today's are still waiting). Low-confidence proposals are corrected or rejected more often (what a calibrated system implies). A mild improvement over the 4 weeks stands in for the learning loop. **Illustrative, not measured** |
| Work | Approved tickets go to a specialist. Everything older than 3 days is `done` (with resolution, closing note and who resolved it); about half of 2-day-old and a sixth of yesterday's are done; the rest are assigned, in progress or waiting for info |
| Hand-backs and reopens | About 7% of dispatched tickets are handed back and redispatched; about 4% of finished tickets are reopened once, so the KPIs aren't trivially 0 |
| Messages | Per department: a short realistic conversation (announcements, hand-offs, follow-ups), automatic escalation posts, and a few direct messages between analysts, specialists and the admin |

The simulated tickets **don't enter the knowledge base**, so they can't affect how real tickets are triaged.

## Saying it honestly in the pitch

- Real: the pipeline, the rules, the live walkthrough, the learning loop, messaging, and every number with the switch off.
- Simulated: the four-week history that makes the trends visible. Say so when you show it; the label is on the screen.
