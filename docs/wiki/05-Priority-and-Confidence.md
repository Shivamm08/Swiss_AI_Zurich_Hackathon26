# 5 · Priority and confidence

Code: `backend/app/pipeline/rubric.py` (priority) and `backend/app/pipeline/confidence.py`.
The rubric is ported from the `feature/apertus-triage` branch and covered by `tests/test_rubric.py`.

## Why rules and not a trained model

In the training data, **Priority, Urgency and Impact are random**. The challenge README says so,
and statistics confirm it: they have no relationship to the ticket text. No model can learn
them. So they are **defined** by rules taken from the challenge's own matrix definitions.

## Service criticality

The challenge lists 14 **Critical** services (Trading Platform, Order Management, Trade Matching,
Securities Settlement, Corporate Actions, Fund Pricing, NAV Calculation, Portfolio Accounting, Cash
Management, Risk & Compliance Monitoring, Regulatory Reporting, SimCorp Dimension, Rimes Data Feed,
Client Reporting). The other 6 are Non-Critical.

## Impact (the matrix's column definitions)

First match wins.

| Condition | Impact |
|---|---|
| No outage, or a service request that isn't a full outage | **Lowest** (no direct impact) |
| Critical service, full unavailability | **Highest** (major / widespread) |
| Critical service, partial degradation | **High** (significant / large) |
| Non-critical, several entities or external counterparties | **High** |
| Non-critical, full unavailability | **Medium** (moderate / limited) |
| Non-critical, only an individual or a team | **Low** (minor / localized) |
| Otherwise (up to one entity) | **Medium** |

## Urgency (the matrix's row definitions)

First match wins.

| Condition | Urgency |
|---|---|
| Regulatory/security breach and no workaround | **Highest** (critical) |
| Critical service fully down | **Highest** |
| Only a difficult workaround exists | **High** |
| Critical service with a hard deadline | **High** |
| Regulatory/security implication | **High** |
| Service request or no outage | **Lowest**, or **Low** if there is any deadline |
| Easy workaround exists | **Medium** |
| Partial degradation | **Medium** if critical, else **Low** |
| Otherwise | **Low** |

## Priority = matrix[Urgency][Impact]

| Urgency ↓ · Impact → | Highest | High | Medium | Low | Lowest |
|---|---|---|---|---|---|
| **Highest** | Highest | Highest | High | Medium | Medium |
| **High** | Highest | High | High | Medium | Low |
| **Medium** | High | High | Medium | Low | Low |
| **Low** | Medium | Medium | Low | Low | Lowest |
| **Lowest** | Medium | Low | Low | Lowest | Lowest |

Because priority is always a lookup in this table, it is **always consistent**, which is what
the challenge scores. If an analyst edits urgency or impact, priority is recomputed the same way.

## The 0–1 priority score (sorting the queue)

Many tickets share the same priority. The score orders them **within** their priority, and can
never move a ticket into another priority level.

```
severity = 0.25 × [service is critical]
         + 0.25 × [regulatory or security breach]
         + 0.20 × [no workaround]
         + 0.15 × [full outage]
         + 0.10 × [several entities or external counterparties]
         + 0.05 × [hard deadline]                                   → 0..1

age      = 0 if resolved, else min(1, days since created / 120)     → 0..1
offset   = 0.7059 × severity + 0.2941 × age

band     = Lowest 0.0–0.2 · Low 0.2–0.4 · Medium 0.4–0.6 · High 0.6–0.8 · Highest 0.8–1.0
score    = band start + 0.004 + 0.192 × offset                      (stays inside the band)
```

**Example:** an alert on a critical service, partially degraded, no workaround, one entity →
Impact High, Urgency Medium → **Priority High** (band 0.6–0.8). Severity = 0.25 + 0.20 = 0.45.
Created today: score **0.665**. Still open after 60 days: **0.693**. It rises within its band,
but never above any Highest ticket.

(The original rubric had a third "difficulty" factor from resolution times. It's switched off
because resolution times in this data are random too.)

## Confidence

An LLM's own "I'm 95% sure" is unreliable. In one test, a model picked the wrong past solution and
still said 0.95. So confidence is built from things we **measure**:

| Part | Question | How it's computed |
|---|---|---|
| **Votes** | Did the 3 votes agree? | Weighted average of per-field agreement (service counts double). Staff-confirmed fields count as 100% |
| **Past-case match** | Have we solved something like this before? | Cosine similarity between the ticket and the matched document, rescaled: 0.30 → 0%, 0.70 → 100%. No match: at most 30%. Match without embeddings: 60% |
| **Flags** | Is there a known reason for caution? | `generic_service` (resolved to "Emailed Support Tickets") × 0.6 · `unclear_input` (request type is nonsense/unclear) × 0.7 |

```
overall = min(votes, past-case match) × flag multipliers
```

Taking the **weaker** part means that if either part is unsure, a human looks. In heuristic mode
(no model), overall is fixed at **20%**.

## Routing

| Overall confidence | Route | What happens |
|---|---|---|
| ≥ 80% | `auto` | Department's Triage inbox, labelled *high confidence*: usually one click for the analyst |
| 50–80% | `review` | Department's Triage inbox, labelled *check carefully* |
| < 50% | `triage` | Shared **Needs review** tab, labelled *low confidence*: even the department may be wrong |

Independently, **Highest priority on a Critical service** sets `escalated = true`. The ticket
appears in the Escalations tab and on the team lead's workload screen. Thresholds are
configurable (`AUTO_THRESHOLD`, `TRIAGE_THRESHOLD`). Nothing is ever assigned or closed
automatically: the analyst dispatches every ticket, and only the specialist marks it done.

## SLA deadlines

| Priority | Deadline |
|---|---|
| Highest | 1 hour |
| High | 4 hours |
| Medium | 24 hours |
| Low | 3 days |
| Lowest | 5 days |

The clock starts when the ticket enters the system (`created_at`). The queue shows a countdown:
amber after 75% of the time has passed, red when overdue.

## Calibration (does confidence mean anything?)

`GET /api/metrics/calibration` groups reviewed proposals by confidence (0–20%, 20–40%, …) and
shows how often analysts accepted them without changing the service or priority. If
the system is honest, higher buckets have higher agreement. Once the evaluation set exists,
this should use its accuracy instead.
