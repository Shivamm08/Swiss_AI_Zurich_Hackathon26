# 1 · What and why

## The challenge

Swiss Life's challenge: *"How might we use AI to help service desk analysts classify, prioritize
and resolve incoming requests faster while keeping humans in control?"*

Swiss Life gave us 20,000 synthetic Jira tickets to learn from and 20 new tickets to triage. For
each challenge ticket we must produce **seven outputs**:

| # | Output | Allowed values | The trap |
|---|---|---|---|
| 1 | **Work type** | Incident · Service Request | Titles are misleading on purpose |
| 2 | **Affected service** | one of 20 services | The service on the ticket is often a wrong guess |
| 3 | **Service team** | one of 11 teams | Must be the team that actually owns the service |
| 4 | **Assignee** | a person | Must be the person implied by the content |
| 5 | **Priority** | Highest · High · Medium · Low · Lowest | Must match the Urgency × Impact matrix |
| 6 | **Resolution** | done · cancelled · clarification · cannot reproduce | Must fit the ticket |
| 7 | **Resolution comment** | free text | Specific and plausible, not "issue fixed" |

Scoring compares our outputs with a hidden answer set. The rules forbid hard-coding answers to
the 20 challenge tickets, so we never tune anything on them.

## What we built

A web app for service-desk staff with three jobs:

1. **Triage.** For every ticket, propose all seven outputs, with the reasoning and the evidence behind them.
2. **Keep humans in control.** Nothing is final until an analyst approves, edits or rejects it.
   Low-confidence tickets go to a human queue.
3. **Get better with use.** Every approved answer becomes knowledge for the next similar ticket.

For the demo, any ticket can be triaged **live**: the screen shows each step as it happens
(retrieval, three AI votes side by side, the priority rules, the confidence, the assignment, the draft).

## Glossary

| Term | Meaning |
|---|---|
| **Intake values** | What the ticket arrived with (service, urgency…). Often wrong on purpose |
| **Proposal** | The AI's suggested answer for a ticket (a `triage_result` row) |
| **Review** | An analyst's decision on a proposal: approve, edit or reject |
| **Facts** | Five observable properties the AI extracts: scope, outage, workaround, regulatory, deadline |
| **Rubric** | Fixed rules that turn facts + service criticality into Impact and Urgency |
| **Matrix** | The challenge's 5×5 table: Priority = matrix[Urgency][Impact] |
| **Priority score** | A 0–1 number that orders tickets *within* the same priority. Never crosses priority levels |
| **Votes** | The AI reads each ticket 3 times independently; how often the answers agree is measured |
| **Confidence** | How sure the system is: the weaker of vote agreement and past-case match, lowered by warning flags |
| **Route** | Where a proposal goes: `auto` (assigned, ≥ 80%), `review` (assigned, marked), `triage` (Needs review queue, < 50%) |
| **Service card** | A short description of one service and its boundaries (20 in total) |
| **Playbook** | The 21 real resolution notes found in the training data, each with its author |
| **Learned ticket** | A ticket an analyst approved, stored as new knowledge |
| **RAG** | Retrieval-augmented generation: find relevant documents first, then let the AI use them |
| **Expert** | The person who resolved the matching past problem. Used for the challenge export |
| **Recommended assignee** | The expert, unless overloaded; then the best available teammate |
| **SLA** | The response deadline, set by priority (e.g. Highest = 1 hour) |
| **Heuristic mode** | Running without an AI model: intake values kept, confidence fixed at 20% |
| **Staff-confirmed field** | A value someone filled in when creating a ticket; the AI must keep it |
| **Copilot** | The chat assistant on every screen; answers from the knowledge base and cites sources |
| **Channel** | A department chat (`team:<Team>`) or a direct message between two people |
| **Escalation** | Asking for urgent ownership: automatic for Highest on critical services, or manual with an AI-drafted message |
| **Simulated history** | Four weeks of generated desk activity for the demo, always labelled, removable |

## Roles in the app

There's no login. A **"View as"** switcher at the top lets you act as any person in the roster.

| Role | Sees | Can do |
|---|---|---|
| **Analyst** | Queue (mine, team, all), Messages, People & teams, Copilot | Approve / edit / reject, reassign, message, escalate |
| **Team lead** | + Needs review, Escalations, New ticket, Team workload, Impact | + handle low-confidence tickets and escalations |
| **Admin** | + Knowledge base, Intake & export, Settings | Everything |

Details: [Collaboration and Copilot](13-Collaboration-and-Copilot.md#personas-view-as).

## The pain points we solve

Misrouted tickets, "everything is urgent", knowledge stuck in people's heads, slow first triage,
one expert getting all the tickets, escalations lost in email, distrust of black-box AI, and vague
tickets. Each has a feature and a live number: see [Impact and demo data](14-Impact-and-Demo-Data.md).

"Analyst" means a human. There is one AI system for the whole desk; the people use it.
