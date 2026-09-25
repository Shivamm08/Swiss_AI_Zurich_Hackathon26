# Triage Copilot: project wiki

![Live triage walkthrough](../images/walkthrough-running.png)

This wiki explains how the whole system works: what it does, how to run it, and what happens
inside when a ticket is triaged. Each page stands on its own, but reading them in order works best.

| # | Page | In one line |
|---|---|---|
| 1 | [What and why](01-What-and-Why.md) | The challenge, the product, and a glossary of terms |
| 2 | [Setup and running](02-Setup-and-Running.md) | Install, run, switch databases, troubleshoot |
| 3 | [Architecture](03-Architecture.md) | Containers, folders, and how a request travels |
| 4 | [Triage pipeline](04-Triage-Pipeline.md) | One ticket, step by step |
| 5 | [Priority and confidence](05-Priority-and-Confidence.md) | The rubric, the matrix, the 0–1 score, confidence, routing, SLA |
| 6 | [Assignment and workload](06-Assignment-and-Workload.md) | Expert vs recommended assignee, workload rules, roster |
| 7 | [Knowledge base and RAG](07-Knowledge-Base-and-RAG.md) | What the AI retrieves from and how it learns |
| 8 | [Data and database](08-Data-and-Database.md) | Dataset facts, tables, migrations, Supabase |
| 9 | [API reference](09-API-Reference.md) | Every endpoint with examples |
| 10 | [Frontend guide](10-Frontend-Guide.md) | Screens, components, and how to add features |
| 11 | [Configuration](11-Configuration.md) | Every `.env` setting |
| 12 | [Development workflow](12-Development-Workflow.md) | Tests, contract, migrations, git rules, CI |
| 13 | [Collaboration and Copilot](13-Collaboration-and-Copilot.md) | Copilot chat, messages, AI-drafted escalations, people, personas |
| 14 | [Impact and demo data](14-Impact-and-Demo-Data.md) | The pain points we solve, the Impact dashboard, the simulated history |
| 15 | [Roles and ticket lifecycle](15-Roles-and-Ticket-Lifecycle.md) | Team Lead / Analyst, Specialist, Admin; from arrival to done |
| 16 | [Screen tour](16-Screen-Tour.md) | Every screen with screenshots |

## The system in 30 seconds

1. A ticket comes in: an imported Jira ticket, a pasted email, or one created in the app (text that
   isn't a ticket at all is rejected at the door).
2. **Retrieval** finds the *relevant* known solutions (only documents at least 40% similar): service
   descriptions, 21 real resolution notes, and every ticket a specialist finished before.
3. **An LLM reads the ticket three times independently** and reports observable *facts*: is
   something broken, how widely, is there a workaround, is there a deadline.
4. **Plain Python rules** turn those facts into Impact and Urgency. The challenge's
   **Urgency × Impact matrix** then gives the Priority. The LLM never picks a priority itself.
5. The system measures **how sure it is**, suggests **who should handle it** (balancing
   workload), and **drafts a suggested resolution**.
6. The department's **Team Lead / Analyst approves, edits or rejects** every proposal. Approving
   dispatches the ticket to a **specialist**.
7. The specialist works the ticket (in progress, waiting for info) and **marks it done** with a
   closing note. Done tickets go into the knowledge base, so the system gets better with use; the
   analyst is notified and can reopen a fix they aren't satisfied with.
   See [Roles and ticket lifecycle](15-Roles-and-Ticket-Lifecycle.md).

Everything in steps 2–5 can be watched live, step by step, in the ticket screen.

Around the pipeline: a **Copilot** chat that answers from the team's knowledge with citations (and
declines off-topic questions),
**messages** between people and departments (with AI-drafted escalations attached to tickets), a
**People & teams** directory, and an **Impact** dashboard with desk KPIs and the service-desk pain
points the system removes. See the [screen tour](16-Screen-Tour.md).
