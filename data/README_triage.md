# Apertus Ticket Triage

Assigns **Work type**, **Impact**, **Urgency**, **Priority**, a continuous
**priority score (0–1)** and a **top-10 similar-ticket ranking** to all 20,000
Jira tickets, using the Swiss AI **Apertus 1.5 70B** model.

```bash
cp .env.example .env         # paste your SWISSCOM_API_KEY into it
pip install -r requirement.txt
python run_triage.py         # ~12 min first run, ~3 s afterwards (cached)
```

Outputs land in `output/`. The headline deliverable is
**`output/jira_triaged.json`** — your input file, same schema, corrected fields.

---

## 1. Read this first: the labels in the training data are random

The challenge README says Priority, Urgency and Impact are "drawn
independently of each other and of the ticket content." That is literally
true, and we verified it:

| Pair | Cramér's V | p-value |
|---|---|---|
| Impact vs Urgency | 0.015 | 0.32 |
| Impact vs Service | 0.032 | 0.36 |
| Urgency vs Service | 0.025 | 0.99 |
| Impact vs Work type | 0.018 | 0.19 |

Nothing is significant. **There is no function from ticket text to these
labels**, so no model can beat the 50.1% majority-class baseline. An earlier
FinBERT attempt scored exactly **0.5008** — precisely the `lowest` base rate
(10,016/20,000). It had collapsed to predicting one class for every row, and
the accuracy metric hid it.

**Consequence: these fields must be *defined*, not *learned*.** This pipeline
encodes the challenge's own matrix as policy rather than training on labels
that carry no information. Scoring rewards Priority that is consistent with the
matrix; here that consistency is structural, not hoped for.

Two fields in the training data *are* trustworthy, and we use them:
`Work type` (to measure accuracy) and `Created date` (for the age factor).

---

## 2. Architecture

```
          ticket text
               |
               v
    +---------------------+
    |   Apertus 70B       |   extracts OBSERVABLE FACTS only
    |   (173 x 3 calls)   |   never names a priority
    +---------------------+
               |  work_type, scope, outage_extent,
               |  workaround, regulatory_or_security, deadline_pressure
               v
    +---------------------+
    |  Deterministic      |   plain Python decision tables
    |  rubric (rubric.py) |   readable, unit-tested
    +---------------------+
               |  Impact, Urgency
               v
    +---------------------+
    |  Priority matrix    |   guarantees matrix consistency
    +---------------------+
               |  Priority + priority_score
               v
    +---------------------+
    |  Similarity engine  |   pure Python, runs AFTER, never feeds back
    +---------------------+
```

**There is no RAG.** Apertus sees one ticket's own Summary, Description and
recorded service — nothing retrieved, no neighbours, no corpus examples. The
similarity engine is an *output*, computed afterwards in Python; it never
enters a prompt. (Adding RAG would be the natural next step for generating
resolution text, which this pipeline does not yet do.)

**The model never decides a priority.** It reports facts; `rubric.py` decides.
That split is what makes the policy auditable and testable.

### Why only 173 model calls for 20,000 tickets

The corpus deduplicates to **173 distinct `(Summary, Description, Service)`
variants** — the data is generated from 11 description templates across 20
services. Each variant is classified once (3× for self-consistency voting =
519 calls) and the result joined back onto all 20,000 rows.

This is **deduplication, not retrieval**. Each variant is judged purely on its
own text; no information flows between tickets at classification time.

Cost: ~180k input / ~42k output tokens ≈ **1.8% of the hackathon budget**.

---

## 3. The priority formula

Four steps. Steps 1–3 give the categorical value; step 4 turns it into a
continuous rank.

### Step 1 — Impact, from the matrix's own column definitions

| Condition | Impact |
|---|---|
| critical service **and** full unavailability | `highest` |
| critical service **and** partial degradation | `high` |
| non-critical **and** (multi-entity or external counterparty) | `high` |
| non-critical **and** full unavailability | `medium` |
| non-critical **and** individual/team scope only | `low` |
| no outage — informational or a service request | `lowest` |

"Critical service" is the 14-service list from the challenge README
(`criticality.md`), not a heuristic.

### Step 2 — Urgency, from the matrix's own row definitions

| Condition (first match wins) | Urgency |
|---|---|
| regulatory/security breach **and** no workaround | `highest` |
| critical service **and** full unavailability | `highest` |
| workaround exists but is difficult | `high` |
| critical service **and** hard deadline | `high` |
| regulatory/security breach | `high` |
| service request, or no outage | `lowest` (`low` if any deadline) |
| easy workaround available | `medium` |
| partial degradation | `medium` if critical, else `low` |
| otherwise | `low` |

### Step 3 — Priority = matrix lookup

```
Priority = MATRIX[Urgency][Impact]
```

The 25-cell table from the challenge README, transcribed verbatim into
`rubric.PRIORITY_MATRIX` and checked cell-by-cell by `test_rubric.py`.

### Step 4 — priority_score, the 0–1 rank

**4a. Severity** — weighted sum of six binary signals (weights sum to 1):

```
severity = 0.25 · [service is critical]
         + 0.25 · [regulatory or security breach]
         + 0.20 · [no workaround]
         + 0.15 · [full unavailability]
         + 0.10 · [multi-entity or external counterparty]
         + 0.05 · [hard deadline]

severity ∈ [0, 1]
```

**4b. Age** — only unresolved tickets accrue waiting cost:

```
        ⎧ 0                           if Status == "done"
age  =  ⎨
        ⎩ min(1, age_days / 120)      otherwise

age_days = (latest Created date in corpus) − (this ticket's Created date)
age ∈ [0, 1]
```

Measured against the corpus's own horizon rather than today's date, so reruns
are reproducible.

**4c. Difficulty** — how long the ticket's peer group took to resolve:

```
peers      = tickets sharing the same (template, service)
difficulty = (median peer resolution time − min) / (max − min)
difficulty ∈ [0, 1], or None when the noise guard rejects it
```

**4d. Combine, then place inside the band:**

```
offset = 0.60 · severity + 0.25 · age + 0.15 · difficulty

  if difficulty is None, its weight is redistributed proportionally:
  offset = 0.7059 · severity + 0.2941 · age

offset ∈ [0, 1]

(lo, hi) = band for the categorical Priority
pad      = 0.02 · (hi − lo)      = 0.004
span     = (hi − lo) − 2 · pad   = 0.192

priority_score = lo + pad + span · offset
               = lo + 0.004 + 0.192 · offset
```

| Priority | Band | Actual score range |
|---|---|---|
| `lowest` | 0.00–0.20 | 0.004 – 0.196 |
| `low` | 0.20–0.40 | 0.204 – 0.396 |
| `medium` | 0.40–0.60 | 0.404 – 0.596 |
| `high` | 0.60–0.80 | 0.604 – 0.796 |
| `highest` | 0.80–1.00 | 0.804 – 0.996 |

**The band is a hard constraint.** Age and difficulty reorder tickets *within*
a band and can never push one across a boundary, so sorting by
`priority_score` always agrees with the categorical Priority — and Priority
always agrees with the matrix. `test_rubric.py` asserts this.

### Worked example

A monitoring alert on Trading Platform (critical service, partial degradation,
no workaround, one entity) → Impact `high`, Urgency `medium` → Priority
`high`, band [0.60, 0.80].

```
severity = 0.25 (critical) + 0.20 (no workaround) = 0.45
```

| Ticket state | age | offset | priority_score |
|---|---|---|---|
| Closed | 0.000 | 0.7059 × 0.45 = 0.318 | **0.6650** |
| Open, 0 days | 0.000 | 0.318 | **0.6650** |
| Open, 30 days | 0.250 | 0.391 | 0.6791 |
| Open, 60 days | 0.500 | 0.465 | 0.6932 |
| Open, 120+ days | 1.000 | 0.612 | **0.7215** |

### Open vs closed, in one line

Closed tickets have `age = 0`, so their score is pure severity and they cap at
**70.6%** of their band; only ageing open tickets reach the top ~29%. Across
the corpus that yields **8 distinct scores over 16,969 closed tickets** and
**1,149 over 3,031 open ones**.

For a live work queue, filter `is_resolved == False`. For severity comparable
across both, use `severity_offset`, which is age-free. `confidence` is separate
too — certainty is not severity.

### The difficulty noise guard

Difficulty is **off** on this dataset, automatically. Before use, the pipeline
measures how much of the variance in resolution time is genuinely explained by
peer group:

```
ε² = (SSB − (k−1)·MSW) / SST        bias-corrected effect size
enabled  ⟺  ε² ≥ 0.01  AND  ANOVA p < 0.01
```

Here: **ε² = 0.00042, p = 0.34 → OFF.** Resolution time in this corpus is a
uniform random draw (KS test vs Uniform[1,21] days: p = 0.32), exactly like
Priority/Urgency/Impact. Feeding it in would add fake precision to the ranking.

> ⚠️ **Do not replace ε² with plain η².** η² is inflated by the number of
> groups: with 173 peer groups, pure noise already yields η² ≈ 0.0101. An
> earlier version used η² against a 0.01 threshold — *below chance level* — and
> silently switched the factor on for pure noise.

On real Jira data, or the challenge set, the guard passes and the factor
activates with no code change.

---

## 4. The similarity formula

### Why not plain text similarity

64% of rows sit in groups of 100+ **byte-identical** tickets (largest group:
4,212). A text-only top-10 returns ten arbitrary rows all scoring 1.000 —
useless. Similarity is therefore computed over **facets**.

### The formula

For two tickets *a* and *b* (weights sum to 1, so the result reads directly on
0–1):

```
sim(a,b) = 0.35 · text(a,b)
         + 0.25 · service(a,b)
         + 0.15 · template(a,b)
         + 0.10 · work_type(a,b)
         + 0.10 · team(a,b)
         + 0.05 · entity(a,b)
```

with each component in [0, 1]:

| Component | Definition |
|---|---|
| `text` | cosine similarity of TF-IDF vectors over `Summary + ". " + Description`; word 1–2 grams, sublinear term frequency |
| `service` | `1.0` same service · `0.30` different service but same criticality rating · `0.0` otherwise |
| `template` | `1` if the same scenario template, else `0` |
| `work_type` | `1` if both Incident or both Service Request, else `0` |
| `team` | `1` if the same Service Team, else `0` |
| `entity` | `1` if the same Business Entity, else `0` |

**No priority or severity term.** Similarity describes what a ticket *is*, not
what was concluded about it. Two identical faults are equally good precedent
regardless of how they were triaged. Excluding it keeps information one-way —
similarity can inform priority reasoning without priority having already shaped
similarity — and prevents the age component of `priority_score` leaking in,
which would otherwise make two identical tickets look less alike purely for
having been raised months apart.

### How the ranking is produced

1. Collapse the 20,000 rows to **864 facet signatures** — distinct
   `(template, service, entity, work_type, team)` combinations.
2. Compute the full 864 × 864 similarity matrix.
3. For each signature take the **top 10** by `sim`, descending. Rank 1 = most
   similar. A signature may match itself (identical past tickets really are the
   best precedent); the querying ticket is then swapped for a sibling row.
4. Each neighbour is represented by **one concrete ticket**, preferring one
   that documents its resolution — the downstream use is drafting resolution
   text from precedent.

Returning one ticket per *signature* keeps the list diverse instead of ten
copies of the same ticket.

### Reading the scores honestly

Typical spread:

| rank | 1 | 2–5 | 6–10 |
|---|---|---|---|
| median similarity | 1.000 | 0.950 | ~0.65 |

Rank 1 is usually a byte-identical sibling; ranks 2–5 sit on a 0.95 shelf; then
a real cliff. The scale is absolute, not rank-normalised — a ticket with no
good match genuinely scores low.

Two columns exist to stop you over-trusting a rank:

- **`neighbour_tie_group_size`** — how many identical tickets that neighbour
  stands for. A rank-1 neighbour representing 4,212 rows is a *class*, not a
  specific match. Median is 76.
- **`neighbour_n_with_resolution`** — how many of those actually document a
  resolution. Only 24.1% of tickets do; 5,851 comments are the bare string
  `"Problem fixed."` 97.6% of rank-1 neighbours have at least one.

---

## 5. Outputs

| File | Rows | Contents |
|---|---|---|
| **`jira_triaged.json`** | 20,000 | **the deliverable** — input schema, corrected fields |
| `jira_triaged.csv` | 20,000 | the same data flat, for spreadsheets |
| `similarity_neighbours.csv` | ~200,000 | 10 rows *per ticket* |
| `decision_audit.csv` | 173 | every distinct decision the pipeline can make |
| `similarity_signatures.csv` | 864 | facet signatures and their representatives |

Similarity is **not a column** on the main table — each ticket has ten
neighbours, so it is a separate long-format table joined on `ticket_id`. The
JSON output inlines it instead.

### `jira_triaged.json`

A drop-in replacement for the input: every original field in its original
order, with `Work type`, `Impact`, `Urgency`, `Priority` **overwritten by the
predictions**. Everything added sits under one `triage` key, so anything that
consumed the original schema still works.

```json
{
  "Work type": "Service Request",
  "Summary": "...", "Description": "...",
  "Priority": "lowest", "Urgency": "lowest", "Impact": "lowest",
  "triage": {
    "priority_score": 0.0738,
    "severity_offset": 0.25, "age_factor": 0.6354, "difficulty_factor": null,
    "combined_offset": 0.3634, "confidence": 0.9444,
    "is_resolved": false, "age_days": 52.87,
    "evidence": { "work_type": "Service Request", "scope": "one_entity",
                  "outage_extent": "none", "workaround": "not_applicable",
                  "regulatory_or_security": false, "deadline_pressure": "none" },
    "original": { "Priority": "low", "Urgency": "high", "Impact": "low" },
    "similar_tickets": [
      { "rank": 1, "ticket_id": "T02335", "similarity": 1.0,
        "tie_group_size": 4, "n_with_resolution": 0 }
    ]
  }
}
```

`triage.original` keeps the randomised source values, so the overwrite loses
nothing. `similar_tickets` is **inlined**, making this file self-contained —
no join needed.

Compact by default (~55 MB for 20k rows). `--json-indent 2` pretty-prints it;
right for the 20-ticket challenge set, wasteful for the full corpus.

### `decision_audit.csv` — the review artefact

173 rows: the pipeline's **entire decision surface**, with the extracted
evidence, the resulting Impact/Urgency/Priority, and the full source
`Description`. Every decision the system can make fits on one page, so the
policy can be checked by hand rather than trusted.

---

## 6. Running it

| Flag | Effect |
|---|---|
| *(none)* | full run; resumes from cache |
| `--dry-run` | rubric + similarity on cached evidence, no API calls (~3 s) |
| `--limit N` | extract only N variants (smoke test) |
| `--refresh` | ignore the cache and re-extract |
| `--top-k K` | neighbours per ticket (default 10) |
| `--json-indent N` | pretty-print the JSON output |

Dependencies: `pandas`, `numpy`, `scikit-learn`. The Apertus client is stdlib
`urllib` — no `openai`, no `torch`, no model download. (`torch` and
`transformers` in `requirement.txt` are only for `classify_service.py`.)

**Endpoint** — note the product path is `swiss-ai-weeks`. The
`swiss-ai-platform` path in Swisscom's public docs is a *different* product
that hackathon keys are not entitled to; it returns `NO_PRODUCT_FOUND_FOR_KEY`:

```
https://api.swisscom.com/products/swiss-ai-weeks/apertus-1.5-70b/v1
model: swiss-ai/Apertus-v1.5-70B
```

**Rate limits.** The hacker guide documents 5 req/s, but the gateway returns
429 well below that under sustained load. The client starts at 2 req/s with 2
workers and widens its own interval on every 429. Evidence caches to
`triage_cache/evidence.json` **after every variant**, so an interrupted run
resumes instead of restarting.

---

## 7. Validation

```bash
python test_rubric.py        # 18 invariants, no API calls needed
```

Covers all 25 matrix cells against the README, that `priority_score` never
crosses a band boundary, that all 1,440 evidence combinations produce a valid
verdict, that age lifts only unresolved tickets, and that a missing difficulty
signal does not silently shrink every score.

**Work type accuracy: 93.9%** against the recorded value.

|  | actual Incident | actual Service Request |
|---|---|---|
| **predicted Incident** | 16,000 | 1,211 |
| **predicted Service Request** | 0 | 2,789 |

Perfect on all 16,000 incidents, zero false positives.

There is deliberately **no accuracy metric against Impact/Urgency** — those
labels are noise, and scoring against them is what produced the misleading
`1.0` in the old FinBERT pipeline, which overwrote the column it was scoring
against and compared predictions to themselves.

---

## 8. Known limitations

**`Email notification received` — 1,211 rows, the entire residual error.** Its
body reads *"An external party sent an email warning… references degraded
service quality, a delayed feed, or a possible outage"* and it is labelled
`Service Request`. The near-identical `External email warning received` (4,212
rows, same service, same generic body) is labelled `Incident`. They are
paraphrases with opposite labels, so no semantic rule separates them. 93.9% is
the ceiling on this data, not a model shortcoming.

**`Emailed Support Tickets` — 5,423 rows (27%) — service is unrecoverable.**
Those tickets name no real service in their text, so criticality cannot be
inferred. They default to non-critical and are flagged `service_unresolvable`.

**Service correction is upstream and not yet wired in.** Impact depends on
service criticality, so a wrong service propagates into Impact.
`classify_service.py` sits at 0.629 and is the highest-leverage remaining fix.

**Comments are not used.** Extraction runs with `comments=""`. The corpus has
only 41 generic comment templates carrying no severity signal, but the
challenge tickets may differ — `build_user_prompt` already accepts them.

**No resolution-text generation.** Deliverable 7 of the challenge is not
implemented. The similarity engine supplies exactly the precedent it needs,
which is where RAG would genuinely earn its place.

---

## 9. Notes for anyone extending this

**Keep the extraction schema constrained.** A free-text `evidence` field was
tried and removed: under vLLM guided decoding it intermittently ran away (one
response emitted 305 lines) or truncated mid-string, breaking the JSON on
roughly one call in ten. The enums and booleans have never failed once.

**Write prompts as an ordered decision procedure, not a rule list.** An early
version phrased the incident/request split as a rule ("if nothing is broken,
set `outage_extent='none'`"). Apertus over-applied it and collapsed **all 173
variants** to `none`/`individual`/`not_applicable` — including the 7,385
monitoring alerts that explicitly describe execution errors. Numbering the
steps (decide work type *first*, derive outage *from* it) and giving one worked
example per dominant template fixed it.

**All judgement belongs in `rubric.py`.** If you find yourself asking the model
for a priority, put it in a table instead.
