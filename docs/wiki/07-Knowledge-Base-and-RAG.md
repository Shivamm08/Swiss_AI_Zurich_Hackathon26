# 7 · Knowledge base and RAG

**RAG (retrieval-augmented generation)** means finding relevant documents first, then letting
the AI use them. Here it grounds the classification, picks the expert, shapes the resolution
draft and feeds the confidence score.

Code: `backend/app/pipeline/retrieve.py`, `backend/app/kb/`.

## What's in the knowledge base

Everything lives in the `kb_documents` table. Each document has a `kind`, a stable `ref_id`, text,
metadata, and an embedding (1,536 numbers from `text-embedding-3-small`).

| Kind | Count | Source file | `ref_id` | What it is |
|---|---|---|---|---|
| **Service card** | 20 | `kb/services.yaml` | `svc-trade-matching` | Description, typical keywords and **boundaries** of one service |
| **Playbook entry** | 21 | `kb/playbook.jsonl` | `pb-trade-matching-2` | A real resolution note from the training data, with its author (`resolver`) |
| **Learned ticket** | grows | created when a ticket is done | `tkt-22` | A ticket a specialist marked done, with the final decision and **their** closing note |

### Service cards

Hand-written, one per service, for example:

```yaml
- name: Trade Matching
  description: Matching executed trades and allocations with brokers before settlement.
  keywords: [allocation, broker, SSI, confirmation, unmatched, rejected, matching adapter, CTM]
  not_this: Once trades are matched and custody status is late, it is Securities Settlement.
```

The `not_this` lines matter most: the challenge deliberately tests the boundaries between
similar services. Improving these cards is the easiest way to improve service accuracy.

### The playbook

The 20,000 training tickets contain only **79 distinct comments**. Most are filler
("Problem fixed." appears 5,851 times). Exactly **21** describe a real fix (root cause, action,
verification), 2–3 per service for 10 services, and **each is always written by the same person**.
`scripts/build_playbook.py` extracts them:

```json
{"id": "pb-trade-matching-2", "service": "Trade Matching",
 "note": "Resolution: Found a missing broker SSI mapping causing allocation rejections. Added the mapping, replayed the rejected messages, and confirmed the trades matched successfully.",
 "resolver": "quinn.anderson@intcom.com", "occurrences": 280, "resolver_share": 1.0}
```

The raw 20,000 tickets are **not** in the knowledge base: they're 173 templates repeated, and
the playbook already holds their useful content. In production you'd build the playbook from
Swiss Life's real resolved tickets and knowledge articles; nothing else changes.

## Loading (sync)

On every backend start, `scripts/sync_kb.py` does the following:
1. Reads `services.yaml` and `playbook.jsonl`.
2. Inserts new documents, updates changed ones (and clears their embedding), and leaves learned tickets alone.
3. Creates embeddings for any document without one (if an embedding model is configured).
4. Loads `roster.yaml` into the `users` table.

You can also trigger it from the Knowledge base screen (**Re-sync from files**) or with
`POST /api/kb/sync`. To regenerate the playbook from the training data: `make build-playbook`.

## Searching (hybrid retrieval)

For a ticket, the query is its full text (see [pipeline](04-Triage-Pipeline.md#what-the-ai-sees)).

1. **Keyword ranking (BM25)** over each document's title + content. Rare words weigh more,
   so exact identifiers match strongly. Parameters: k1 = 1.5, b = 0.75.
2. **Vector ranking:** the query is embedded, and pgvector returns the nearest documents by
   cosine distance.
3. **Merge (reciprocal rank fusion):** each document scores `Σ 1 / (60 + rank)` across both
   lists. The top 6 are returned, scores normalised so the best = 1.00.

Without an embedding model, only step 1 runs. Everything still works, just less well on paraphrases.

## What the retrieved documents are used for

| Use | How |
|---|---|
| **Classification** | All 6 go into the extraction prompt (service boundaries, known fixes) |
| **Matched solution** | The LLM names the matching playbook entry (`playbook_ref`); it must be one of the retrieved ones and belong to the chosen service. Otherwise the best learned ticket on that service is used |
| **Expert** | The matched document's `resolver` |
| **Draft** | The matched note is the template for the resolution comment |
| **Confidence** | Cosine similarity to the matched document → the "past-case match" part |
| **Assistant** | The chat answers from the top 5 documents and cites them as `[ref_id]` |

## The learning loop

When a specialist **marks a ticket done** (`POST /api/tickets/{id}/work` with `resolve`,
then `kb/learn.py`):

1. A document `tkt-<number>` is created or updated, with the ticket's summary and description,
   the final classification (the analyst's edit if there was one, else the approved proposal),
   the resolution type, and the specialist's **own closing note**.
2. `meta.resolver` = the specialist who resolved it; `meta.quality` = `resolved`.
3. It is embedded immediately.

The next similar ticket then retrieves this **real, finished** fix. It often ranks first,
above the playbook. This raises the past-case confidence, gives a better draft, and builds
expertise for the specialist (see [assignment](06-Assignment-and-Workload.md)).

**Only finished work enters the knowledge base**: never raw AI output, and never a ticket that
was only approved at triage and hasn't been worked yet. Otherwise the system would learn from
guesses. See [Roles and ticket lifecycle](15-Roles-and-Ticket-Lifecycle.md).

## Copilot chat

The Copilot (on every screen, ⌘K) uses the same retrieval: for each question it fetches the top 5
documents (plus the ticket, if one is open) and answers **only from them**, citing `[ref_id]`,
streaming word by word, with the conversation remembered. Without a model it lists the most
relevant sources. Details: [Collaboration and Copilot](13-Collaboration-and-Copilot.md).
The older single-shot endpoint `POST /api/assistant/ask` still exists.
