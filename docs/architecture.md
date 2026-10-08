# Architecture — Condition Briefing for Health-System Strategists

Intent: `docs/condition-briefing.prd.md`. Stack baseline: `research/tech-stack.md` (verified in the 2026-10-07
dry run, `docs/runbook-kickoff.md` → Dry-run lessons).

## Problem & goals

A health-system strategist enters a medical condition and needs, in under a minute, a briefing in three sections
(current standard of care, emerging treatments, key companies/institutions) where every claim cites a source and
nothing lands in the wrong section. Every decision below is judged against the PRD's WRONG condition: more than 1
in 10 briefings with an unsupported claim or a wrong-section claim fails the bet.

## Approaches considered

| Approach | Shape | Trade-off | Call |
|---|---|---|---|
| **A. Fixed four-stage pipeline, two decision points** | Planner → retriever (function) → answerer → critic, with one critic → answerer retry | Predictable, testable stage by stage; autonomy only where a choice exists | **Chosen** |
| B. One tool-using model in a loop | Model calls a search tool per section and decides when it's done | Real autonomy, but slower, less predictable, harder to evaluate; nothing in the PRD needs it | Rejected |
| C. Functions plus one model call | Fixed retrieval, one drafting call, code checks only | Simplest, but the drafter checks its own work and the multi-agent rubric item is lost | Rejected |

**Why A, for the stakeholder:** the retriever is a function, not an agent. There are two decision points, the
planner's routing and the critic's gate, each a separate model call with its own prompt and typed contract, so the
stage that writes the briefing never also approves it.

## Recommended approach

A strategist's request goes through four stages. The **planner** classifies it: a briefing for a known condition,
a follow-up about the current briefing, or out of scope (clinical/patient advice, unknown condition, anything
else), which is refused before any retrieval runs. It also resolves the condition name to a condition in the
corpus. The **retriever** runs three searches, each filtered to that condition and one section, so every section
draws only on evidence labeled for it. The **answerer** drafts the three-section briefing from those passages,
citing a source for every claim. The **critic** runs code checks first, then a model check for faithfulness, and
either passes the briefing, sends it back to the answerer once, or refuses. The result is streamed to the UI and
returned as JSON for evals.

## Key decisions

- **Stack & libraries:** unchanged from `research/tech-stack.md`. Anthropic Messages API with structured output
  through one shared helper; `claude-haiku-4-5` for planner and critic, `claude-sonnet-5-5` for the answerer
  (dry-run settings). FastAPI with SSE, Supabase Postgres + pgvector, Voyage `voyage-4` at 1024 dims, Streamlit,
  Langfuse. *Alternatives:* none reopened; every library here passed the dry run, and the project rule is no
  untested library.
- **Retrieval:** semantic search with a hard metadata filter (condition + section), top-k per section. Keyword
  search is deferred: once filtered to one condition and one section the candidate set is a handful of chunks,
  so hybrid ranking adds little. *Alternative:* hybrid keyword + semantic, as discussed on the call. Reversible;
  add it if the eval hit rate is short. **Tell the stakeholder about this change in the walkthrough they asked for.**
- **Data model (shape):**
  - **Condition**: canonical name plus aliases, so the planner can resolve "CHF" to heart failure.
  - **Document**: one source, belonging to exactly one condition and one section, with a title, a source label,
    and an as-of date (the date answers the stakeholder's freshness concern on screen).
  - **Chunk**: ordered piece of a document with its embedding; condition and section are carried on the chunk so
    the search filter is a single-table query. Stable chunk ids, so re-ingest never duplicates.
  - **Memory**: a session (conversation turns, including the current briefing) and a per-user profile (recently
    briefed conditions), both scoped by user.
- **Output contract:** keep `AskResponse` in `evals/contract.py`. `answer` is the briefing as markdown with three
  fixed section headings; `citations` are chunk ids from `retrieved`. One additive change: `RetrievedChunk` gains
  optional `section`, `source_label`, and `as_of`, so the UI can show the label and date next to each cited claim
  (the stakeholder walkthrough depends on it). Optional fields keep existing eval cases valid.
- **Guardrails (in code, on typed models):**
  - Scope: refuse clinical or patient-specific advice, conditions not in the corpus, and unrelated questions.
  - PII: redact patient identifiers in the input before anything is stored or sent on.
  - Citations: every claim cites at least one chunk, and every cited chunk was actually retrieved.
  - **Domain rule, section integrity:** a claim in a section may only cite chunks labeled with that section. This
    is the code form of the PRD's wrong-section failure.
  - Critic retries the answerer once, then refuses; it never passes an unchecked briefing.
- **Boundaries & contracts:** secrets (Anthropic, Voyage, Supabase, Langfuse) in `.env` / Render env only. Every
  new table has row level security enabled with no policies, so Supabase's public REST API can't reach it. The
  corpus is synthetic, so no real health data or PHI enters the system; HIPAA is out of scope by construction.
  External calls: Anthropic, Voyage, Supabase, Langfuse; nothing else.
- **Memory scope:** session memory serves follow-ups about the current briefing (answered from the same
  retrieved evidence); persistent memory shows the strategist's recent conditions in the UI. Both visible in the
  UI, per the rubric.

## Missing pieces

- ~~**Synthetic corpus**~~ **done**: `corpus/condition-briefing/` (30 documents, data card in its README, checked
  by `scripts/check_corpus.py`). Walkthrough for the stakeholder: `docs/walkthrough-data.md`.
- **Schema for conditions, documents, chunks, sessions, profiles** as new numbered migrations.
- **Ingest** that reads the labels, chunks, embeds as documents, and upserts.
- **The four stages and the pipeline**, behind `POST /ask` (JSON) and `POST /chat` (SSE).
- **Golden set** `evals/golden/condition-briefing.yaml`: 10 answerable conditions plus out-of-scope (unknown
  condition, clinical advice), PII, and section-integrity cases.
- **UI chat view**: condition input, three-section briefing with citations and as-of dates, recent conditions.

## Spikes & experiments

- **Section labeling (the one-way door): spike skipped by decision (2026-10-08).** Going ahead on the stated
  assumption that section-labeled synthetic documents give each section clean evidence. Accepted risk. **Trigger
  to revisit:** if the golden-set hit rate or the section-integrity check fails on more than 1 in 10 conditions
  after the first ingest, revisit chunk size and labeling before tuning prompts.

## Open questions

- [ ] Is sample/synthetic data acceptable to the stakeholder given the freshness and credibility concern? Settled
      by showing as-of dates and source labels in the walkthrough.
- [ ] Regulatory posture: we assume synthetic data, internal tool, no PHI. Settled by stating it to the
      stakeholder and noting their answer.
- [ ] Cost of a wrong answer: hard refusal after one retry is assumed. Settled by the stakeholder's reaction to a
      refused briefing in the demo.
- [ ] Keyword search: deferred. Settled by the first eval run's hit rate.
- [ ] Release 2 (freshness monitoring, live sources, cross-condition reasoning): not discussed; out of this build.
- [ ] Which parts of the setup kit the prototype uses (stakeholder's orchestration concern): answered by this
      doc's approach table; confirm in the walkthrough.
