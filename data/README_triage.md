# Apertus triage pipeline

Assigns **Impact**, **Urgency**, **Priority**, a continuous **priority score
(0–1)**, and a **top-10 similar-ticket ranking** to all 20,000 tickets.

## Why this is not a supervised model

`Impact` and `Urgency` in the training set are random by construction — the
challenge README says so, and it checks out:

| Pair | Cramér's V | p |
|---|---|---|
| Impact vs Urgency | 0.015 | 0.32 |
| Impact vs Service | 0.032 | 0.36 |
| Urgency vs Service | 0.025 | 0.99 |

No function maps ticket text to these labels, so nothing can beat the 50.1%
majority-class baseline. The earlier FinBERT run scored **0.5008**, which is
exactly the `lowest` base rate (10016/20000) — it had collapsed to predicting
one class for every row.

So these fields are **defined**, not learned. Scoring rewards Priority that is
consistent with the matrix, which this pipeline guarantees structurally.

## Architecture

```
Apertus 70B          ->  deterministic rubric  ->  matrix lookup
(reads messy text)       (encodes the policy)      (guarantees consistency)
   evidence JSON             Impact/Urgency            Priority + score
```

The model never names an Impact or Urgency. It only reports observable facts
(scope, outage extent, workaround, regulatory exposure, deadline, request-vs-
incident). All judgement lives in `rubric.py` as readable tables.

**20,000 rows cost 173 extractions.** The corpus collapses to 173 distinct
(Summary, Description, Service) variants; results are joined back onto every
row. With 3-vote self-consistency that is 519 calls, ~1.8% of the token budget.

## Setup

```bash
cp .env.example .env        # then paste your key into it
python run_triage.py
```

No new dependencies — uses `pandas`, `numpy` and `scikit-learn`, which are
already installed. The Apertus client is stdlib `urllib`, so there is no
`openai`/`torch`/`transformers` requirement and nothing to download.

| Flag | Effect |
|---|---|
| *(none)* | full run; resumes from cache |
| `--limit N` | extract only N variants (smoke test) |
| `--dry-run` | rubric + similarity on cached evidence, no API calls |
| `--refresh` | ignore the cache and re-extract |
| `--top-k K` | neighbours per ticket (default 10) |

Evidence caches to `triage_cache/evidence.json` **after every variant**, so an
interrupted run resumes instead of starting over.

### Rate limits

The hacker guide documents 5 req/s, but the gateway returns 429 well below
that under sustained load. The client starts at 2 req/s with 2 workers and
widens its own interval on every 429 (it never speeds back up mid-run).
Failed variants get one cool-down retry pass before the run gives up.

## The two scores

### `priority_score` — 0 to 1

The categorical priority fixes a band; severity sub-signals order tickets
*within* it. Sorting 20,000 tickets by this number can never contradict the
graded matrix.

| Priority | Band |
|---|---|
| lowest | 0.00–0.20 |
| low | 0.20–0.40 |
| medium | 0.40–0.60 |
| high | 0.60–0.80 |
| highest | 0.80–1.00 |

Within-band position is a weighted blend: critical service (0.25), regulatory
or security exposure (0.25), no workaround (0.20), full outage (0.15), broad
scope (0.10), hard deadline (0.05).

`confidence` is reported **separately** (agreement across the 3 votes).
Severity and certainty are different questions and mixing them into one number
would make both unreadable.

### `similarity` — 0 to 1, ranked 1–10

Pure text similarity is degenerate here: 64% of rows sit in groups of 100+
byte-identical tickets (largest group 4,212), so a text-only top-10 returns ten
arbitrary rows all scoring 1.000. Similarity is therefore **faceted**:

| Facet | Weight |
|---|---|
| TF-IDF text cosine | 0.30 |
| Service (1.0 exact, 0.3 same criticality) | 0.25 |
| Scenario template | 0.15 |
| Work type | 0.10 |
| Service team | 0.10 |
| Business entity | 0.05 |
| Severity proximity | 0.05 |

Weights sum to 1.0, so the score is an honest absolute scale — a ticket with no
good match genuinely scores low rather than being rank-normalised upward.

Neighbours are returned **one per facet signature** (864 exist) so the list is
diverse rather than ten copies of the same ticket. Two honesty columns come
with each neighbour:

- `neighbour_tie_group_size` — how many identical tickets that neighbour stands
  for. A rank-1 neighbour representing 4,212 rows is a *class*, not a match.
- `neighbour_n_with_resolution` — how many of those actually document a
  resolution. Only 24.1% of tickets do; 5,851 comments are the bare string
  "Problem fixed." Representatives prefer tickets that document their
  resolution, since the downstream use is drafting resolution text from
  precedent.

## Outputs (`output/`)

| File | Contents |
|---|---|
| `jira_triaged.csv` | all 20k rows with Impact/Urgency/Priority, score, confidence, evidence |
| `similarity_neighbours.csv` | per ticket: 10 neighbours, rank, similarity, tie-group size |
| `decision_audit.csv` | **every distinct decision the pipeline can make** — 173 rows |
| `similarity_signatures.csv` | the 864 facet signatures and their representatives |

`decision_audit.csv` is the review artefact: the entire decision surface fits on
one page, so the whole policy can be checked by hand rather than trusted.

## Validation

```bash
python test_rubric.py
```

Checks all 25 matrix cells against the README, that `priority_score` never
crosses a band boundary, and that all 1,440 evidence combinations produce a
valid verdict — plus invariants like *critical service + full outage ⇒
highest*, and *routine access request ⇒ lowest*.

There is deliberately **no accuracy metric against the training Impact/Urgency**.
Those labels are noise; scoring against them is what produced the misleading
`1.0` recorded by the former FinBERT `classify_impact.py` (it overwrote the
column it was scoring against, comparing predictions to themselves) and the
`0.5008` from `classify_urgency.py`, which was exactly the `lowest` base rate —
the model had collapsed to one class for all 20,000 rows. Both scripts, their
model directories and the `Data_Cleaning.py` chain that orchestrated them have
been removed; `triage/` replaces them.

`Work type` **is** trustworthy, though — the README only randomises
Priority/Urgency/Impact. So each run reports agreement between the extracted
`is_request` and the recorded `Work type`. That is the one honest accuracy
number available here, and it is a genuine check on the extraction step.

### A note on prompting an open model

The extraction prompt is a numbered decision procedure with worked examples,
not a list of rules. An earlier version phrased the request/incident
distinction as a rule ("if nothing is broken, set `outage_extent='none'`") and
Apertus over-applied it, collapsing **every** variant to
`none`/`individual`/`not_applicable` — including the 7,385 monitoring alerts
that explicitly describe execution errors and degradation. Ordering the steps
(decide incident-vs-request *first*, then derive outage from that) and giving
one worked example per dominant template fixed it. Worth remembering if you
extend the schema: state the decision order, and show an example.

## Known limitations

- **`Emailed Support Tickets` (5,423 rows, 27%) is unrecoverable.** Those
  tickets read *"External email warning received for Emailed Support Tickets"* —
  the text names no real service, so criticality cannot be inferred. They
  default to non-critical and are flagged `service_unresolvable`.
- **Service correction is upstream of this.** Impact depends on service
  criticality, so a wrong service propagates into Impact. The existing
  `classify_service.py` sits at 0.629 and is the higher-leverage thing to fix.
- Extraction runs without ticket comments (`comments=""`). The corpus has only
  41 generic comment templates carrying no severity signal, but the challenge
  tickets may differ — `build_user_prompt` already accepts them.
