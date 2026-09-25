# 13 · Collaboration and Copilot

Service desks lose time **between** tools: the ticket is in Jira, the discussion in email or chat,
the knowledge in someone's head. Triage Copilot keeps all three next to the ticket.

## Copilot (the chat assistant)

A chat panel that slides in from the right on **every screen**. Open it with the **Copilot** button
in the top bar, **Ask Copilot** in the sidebar, or **⌘K / Ctrl+K**. Close it with Esc.

| Feature | How it works |
|---|---|
| **Grounded answers** | For each question it retrieves the 5 most relevant knowledge documents (service cards, playbook, learned tickets) and answers only from them |
| **Citations** | Answers cite sources as `[ref_id]`; each shows as a chip under the answer. Click a chip to see the source |
| **Streaming** | Words appear as they're generated, with a typing indicator and a caret. **Stop** interrupts |
| **Conversation memory** | The last 10 messages are sent with each question, so follow-ups work ("and who usually fixes that?") |
| **Ticket context** | On a ticket page the ticket is attached automatically ("#21 in context"); remove it with ×. Suggestions change to ticket-specific ones |
| **Model** | Uses the model picked in the top bar |

API: `POST /api/assistant/stream` with `{messages: [{role, content}], ticket_id?, model?}` returns
server-sent events: one `sources` event (the citations), many `token` events, then `done` (or `error`).
Code: `backend/app/api/knowledge.py` (`stream_copilot`), `frontend/src/copilot/`, `frontend/src/api/copilot.ts`.

Without an AI model the Copilot lists the most relevant sources instead of answering.

## Messages

Real team chat stored in the database (`messages` table), refreshed every few seconds.

| Channel | Id format | Who |
|---|---|---|
| **Department channel** | `team:<Team name>` | One per team (11); everyone in the roster team |
| **Direct message** | `dm:<email>\|<email>` (sorted) | Two people. Start one with the ✚ button, or from People & teams |

Messages have a **kind** that changes how they look:

| Kind | Looks like | Created by |
|---|---|---|
| `message` | Normal chat bubble | Anyone |
| `resolved` | Bubble with a green "ticket done" tag and the ticket card | Sent automatically from the specialist to their department's **Team Lead / Analyst** when they mark a ticket done: resolution + closing note |
| `handoff` | Bubble with a violet "handed back" tag | Posted automatically in the department channel when a specialist **hands a ticket back** |
| `escalation` | Bubble with a red "escalation" tag. **Sets the ticket's `escalated` flag** and logs it on the ticket | "Escalate" on a ticket (only the specialist on it, its Team Lead / Analyst, or an admin: `403` otherwise) |
| automatic escalation | Red card "Automatic escalation" | The pipeline, when a ticket becomes Highest on a critical service |

A message can carry a ticket: it's shown as a card linking to the ticket.

API: `GET /api/chat/channels?as_user=`, `GET /api/chat/messages?channel=`, `POST /api/chat/messages`.
Code: `backend/app/chat.py`, `backend/app/api/chat.py`, `frontend/src/pages/MessagesPage.tsx`.

## Escalate, hand back, ask: three different things

Before, "escalate" and "hand off" were both just messages. Now each does its own job:

| | Escalate | Hand back | Ask a question |
|---|---|---|---|
| **Means** | "This needs more attention or authority now": SLA at risk, blocked, needs a decision | "I can't take this one": wrong department, at capacity, needs other skills | "I need information" |
| **Who** | The specialist on it, the department's Team Lead / Analyst, an admin | The specialist on it (or an admin) | Anyone |
| **Goes to** | One level up: specialist → their **Team Lead / Analyst**; analyst → the **Admin**; or the department channel | The department's analyst (Triage inbox, shown as *handed back*) | The analyst, the specialist, or the channel |
| **Changes** | `escalated = true`, in the Escalations tab, logged. The assignee stays | Assignee cleared, `work_status` back to `open`; the next suggestion skips that specialist; a "handed back" post in the channel | Nothing |
| **Ends** | **De-escalate** by the department's analyst or an admin (`POST /api/tickets/{id}/deescalate`) | The analyst re-dispatches | – |
| **Where** | **Escalate** button on the ticket → Copilot drafts the message | **Hand back…** in the specialist's work bar (reason required) | **Message about this ticket** |

Specialists don't pass tickets to each other: deciding who works on what is the analyst's job.

### The AI-drafted message

On a triaged ticket, **Escalate** or **Message about this ticket** opens a dialog:

1. Pick the purpose: **Escalate** (only shown if you may escalate this ticket) or **Ask a question**.
2. Pick the recipient. Escalations offer the next level up (see above) or the department channel;
   questions offer the Team Lead / Analyst, the specialist on the ticket, or the channel.
3. **Draft with Copilot.** The AI writes 3–5 sentences with the ticket number, what's affected,
   the priority, the SLA deadline and one concrete ask (`POST /api/chat/draft`).
4. Messages opens on the right conversation with the draft ready. **Edit it, then send.** Nothing
   is sent without a human.

## Automatic escalation

When triage decides a ticket is **Highest priority on a critical service**, it's marked
`escalated`, and a red **automatic escalation** is posted to the owning team's channel, with the
ticket, the suggested specialist and the SLA, asking the Team Lead / Analyst for a decision now. It also appears in the Escalations tab and on the Team
workload screen.

## People & teams (directory)

Every department as a card: the services it owns (critical ones marked), open tickets, people,
messages in the last 7 days, the lead, and the members. **View team** opens a panel with each
person's load (open tickets vs capacity) and a message button; **Message** opens the team channel.
API: `GET /api/directory`.

## Personas ("View as")

There is no login. The **persona button** (top right) opens a panel with:
- **Demo personas:** the admin, the Team Lead / Analyst with the busiest department, the busiest specialist. One click to switch.
- **Everyone, grouped by department**, with role and current load, plus a search box.

The role changes what the sidebar shows:

| Role | Workspace | Manage | Administration |
|---|---|---|---|
| Specialist | Queue (My work…), Messages, People & teams | – | – |
| Team Lead / Analyst | Queue (Triage inbox, Needs review…) ✓ | New ticket, Team workload, Impact | – |
| Admin | ✓ | ✓ | Knowledge base, Intake & export, Settings |

The knowledge base is admin-only because everyone else gets knowledge where they need it (the
evidence on each ticket and the Copilot) instead of browsing documents.
