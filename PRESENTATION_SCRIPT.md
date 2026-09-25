# 1-Minute Investor Pitch — Script

**Target: 155 words ≈ 60 seconds at presentation pace.**
Read it once out loud with a timer before you go on.

---

## THE SCRIPT — say exactly this

> **[0:00 – 0:11] The problem**
>
> At every asset manager, a human reads each ticket and guesses: how urgent, and
> who fixes it. In a regulated firm, a wrong guess is a compliance event.

> **[0:11 – 0:22] What we built**
>
> We rebuilt it around three roles: an Admin raises the ticket, a Team Lead
> assigns it, a Specialist solves it. The Admin types a title and description —
> nothing else.

> **[0:22 – 0:30] The AI**
>
> Our AI fills in the rest — entity, service, impact, urgency. It runs on
> Apertus, and other models. The AI is based on a hybrid LLM-RAG system which iteratively
> learns from the human feedback.

> **[0:30 – 0:43] Differentiator 1 — pause before "not AI"**
>
> But the priority is **not** AI. It's a formula: a score from zero to one,
> weighting the ticket's age, how many entities are hit, whether a regulatory
> breach is in play. **No hallucinated priorities.**

> **[0:43 – 0:48] Human in control**
>
> The Team Lead stays in control — approve, edit, or reject.

> **[0:48 – 1:00] Differentiator 2 — the compounding asset**
>
> And every decision the Team Lead approves writes itself back into the
> knowledge base. The next similar ticket retrieves it. **It compounds on your
> data — and it only ever learns from what a human approved.**

---

## Delivery notes

- **You have two differentiators, not one.** The formula (no hallucinated
  priorities) and the learning loop (it compounds). Land both.
- **Land the pause before "not AI."** Everyone else in the room is selling an
  LLM wrapper; you are selling the opposite.
- **"only ever learns from what a human approved"** is the line that separates
  you from every self-training system that drifts. Do not drop it.
- Do **not** say "hackathon", "synthetic data", or "we didn't have time to".
- Do **not** read the numbers out. They are for the Q&A, not the minute.
- If you only get 30 seconds: keep the problem, "priority is a formula, not a
  guess", and "every approval makes the next ticket route better." Drop the rest.

---

## The one-sentence version (if someone asks in a lift)

> We triage IT tickets with AI, but the priority is pure mathematics — so it's
> explainable to a regulator — and every human approval feeds a retrieval loop
> that makes the next ticket route better. All on Swiss sovereign AI.

---

## Q&A backup — numbers you can defend

Only use these if asked. Every one is measured, not estimated.

| Question | Answer |
|---|---|
| "Does it actually work?" | 20,000 tickets triaged end to end. Work-type classification 93.9% against ground truth. |
| "How is priority calculated?" | `score = 0.60·severity + 0.25·age + 0.15·difficulty`, placed inside a band fixed by the Impact × Urgency matrix. Full formula documented in `data/README_triage.md`. |
| "What stops the AI hallucinating a priority?" | The model is never asked for one. It reports six observable facts as fixed enum values; a lookup table does the rest. 18 automated tests enforce it. |
| "Isn't it expensive at scale?" | 20,000 tickets cost 1.8% of our compute budget — the corpus collapses to 173 distinct cases, so we classify each once. |
| "What if the LLM is down?" | The system runs with the model switched off, on a deterministic fallback path. |
| "Does it improve over time?" | Yes, and measurably. Every approved or edited decision is written back as a retrievable, embedded document, keyed to the service and the resolver. The next similar ticket retrieves it as precedent — for both the drafted resolution and the recommended owner. |
| "How do you stop it learning its own mistakes?" | Only human-approved or human-edited decisions enter the knowledge base — never raw model output. A rejected proposal writes nothing and returns to the triage queue. |
| "So the moat is the data?" | The moat is the *approved* data. Each customer's knowledge base is built from their own analysts' decisions on their own services and staff, so it is not transferable to a competitor and it gets better the longer they run it. |
| "Why Apertus?" | Swiss sovereign, open-weights, hosted by Swisscom. For a Swiss asset manager, data residency is a procurement requirement, not a preference. |
| "How do you avoid over-loading one person?" | Assignment scores `0.6·expertise + 0.4·availability` and blocks anyone at capacity. Workload is visible to every role. |

### If challenged on "how much is really AI?"

Answer honestly and turn it into the strength:

> The LLM does one job: turning free text into structured facts. Every decision
> a regulator would question — impact, urgency, priority, routing — is a
> deterministic formula. That's deliberate. It's what makes the system auditable.

---

## Slide plan (5 slides, 12 seconds each)

| # | Slide | Content |
|---|---|---|
| 1 | **The problem** | One line: *"A human reads every ticket and guesses."* |
| 2 | **The flow** | `presentation_flow.svg` — the role diagram |
| 3 | **The formula** | The priority formula, large. This is the money slide. |
| 4 | **Human in control** | Team Lead approve / edit / reject |
| 5 | **The close** | AI-written resolution → knowledge captured |

Insert the diagram in PowerPoint via **Insert → Pictures → This Device →
`presentation_flow.svg`**. It is native SVG, so it stays sharp when projected
and you can ungroup it to animate the flow step by step.

---

# 1-Minute Technical Walkthrough — `features_overview.svg`

A second, separate minute. Use this when you have the **features diagram** on
screen and the audience is technical (judges, engineers, a CTO) rather than
investors. It covers four things: the rules, retrieval, the learning loop, and
how the model writes resolution notes.

**156 words ≈ 60 seconds.**

## THE SCRIPT — say exactly this

> **[Frame — gesture at the whole page]**
>
> The whole system on one page. The AI reads and writes; the rules decide.
> Four things make it work.

> **[Point at the teal box, centre]**
>
> First, the rules. The model never picks a priority — it reports facts: is
> something down, how widely, is there a workaround, a deadline at risk. Rules
> turn those into Impact and Urgency; the matrix gives Priority.

> **[Point at step 2, top row]**
>
> Second, retrieval. Before the model sees the ticket we search the knowledge
> base — service cards and twenty-one resolution playbooks — keyword and vector
> search combined.

> **[Point at the green box, right]**
>
> Third, it learns. When a specialist marks a ticket done, their closing note
> becomes searchable precedent. Reopen the ticket and it's removed — so it never
> learns from a fix that didn't hold.

> **[Point at step 7, top row]**
>
> Fourth, the model writes that note: root cause, action, verification, grounded
> in the matched past fix. With no precedent it won't invent one; it writes
> diagnostic steps instead.

> **[Close]**
>
> The AI does language. The rules do judgement. Every closed ticket makes the
> next one faster.

---

## Delivery notes

- **Pointing order is not left-to-right:** centre → top-left → right →
  top-right → step back. Beats 2 and 4 are both in the top pipeline row while
  1 and 3 are in the middle band. Rehearse the hand movement once.
- **The fourth beat is the strongest — do not rush it.** "It won't invent one"
  is the line that separates this from every other RAG demo in the room.
- Say **"closing note"** or **"resolution note"**, not "summary". The system
  does not summarise tickets; it writes the resolution, grounded in precedent.

## If you have ten spare seconds, add this

> When retrieval finds no match, the prompt switches. Instead of a resolution
> it writes "No matching past fix — suggested first steps", and numbers them.
> Claiming a fix it hasn't got would be the hallucination.

That is verbatim the reasoning in `backend/app/pipeline/draft.py`:

> *"Without a matching past fix there is nothing true to report yet, so the
> draft is a plan, not a resolution: writing 'I fixed X' here would be a
> hallucination."*

The main prompt also bans filler explicitly — *"No filler such as 'issue
fixed'"* — which is a direct hit on the challenge's scoring criterion about
generic resolution text.

## Q&A backup for this deck

| Question | Answer |
|---|---|
| "What exactly is retrieved?" | 20 service cards with explicit boundaries, 21 real resolution playbooks from the training data, plus every ticket a specialist has finished. BM25 and pgvector run in parallel and are merged by reciprocal rank fusion. |
| "Is the priority ever model-generated?" | No. The model returns six enum fields. `rubric.py` maps them to Impact and Urgency, and the challenge matrix gives Priority. The 0–1 score only reorders tickets *inside* their priority band. |
| "How does the loop avoid drift?" | Only finished work enters the knowledge base, carrying the specialist's own closing note. Reopening a ticket deletes its entry, so a fix that failed in the field stops being precedent. |
| "What if the resolution draft is wrong?" | It is a draft on a ticket a human already approved, and the specialist edits it before closing. The edited version — not the model's — is what gets stored. |
