# Implementation Report — Condition briefing pipeline (T1, pane A)

**Plan**: `.claude/plans/A-condition-briefing-t1.md`   **Branch**: `pane-a`   **Status**: COMPLETE (retrieval stubbed until pane B merges)

## Summary
`POST /ask`, `POST /chat` (SSE) and `GET /recent` now run planner (haiku) → retriever (3 section-filtered
searches) → answerer (sonnet, typed draft) → critic (code checks, then haiku faithfulness; one retry, then refuse).
Guardrails (scope, PII redaction on input, citations ⊆ retrieved, section integrity) are code over Pydantic models.
Memory keeps session turns (follow-ups reuse the briefing's chunks) and per-user recent conditions.

## Tasks completed
- Settings (note 1 + model ids, `retrieval_k`) → `api/config.py` (UPDATE)
- `anthropic` dependency → `api/pyproject.toml`, `api/uv.lock` (UPDATE)
- Schemas → `api/schemas/{__init__,contract,agents}.py` (CREATE)
- LLM helper + errors → `api/agents/{llm,errors}.py` (CREATE)
- Guardrails → `api/guardrails/{__init__,pii,scope,citations}.py` (CREATE)
- Memory → `api/memory/{__init__,store}.py` (CREATE)
- Agents → `api/agents/{planner,retriever,answerer,render,critic,pipeline,deps}.py` (CREATE)
- Routes → `api/main.py` (UPDATE)
- Docs → `.env.example`, `CLAUDE.md` map + rubric rows (UPDATE)

## Tests added
- `tests/test_guardrails.py` (24): PII per identifier kind, aliases untouched, alias/longest-match resolution, scope table, section-integrity rejection, uncited/unretrieved/empty sections.
- `tests/test_pipeline.py` (17): 4 refusal paths with zero searches, model refusal, happy path (status order, tokens after critic, 3 headings, citations ⊆ retrieved, labels + dates, models), alias hint, section-integrity → retry → pass, retry → refuse (no draft text streamed), faithfulness retry, no evidence, follow-up without search, follow-up with no briefing, cross-user session, recent newest first, PII redacted before planner + storage, LLMError.
- `tests/test_routes.py` (8): `/ask` shape, 422, 503 names the class only (LLMError, psycopg), `/chat` event order + error event, `/recent`.
- `tests/test_memory.py` (1, integration): `PgMemoryStore` round trip with cleanup — needs pane B's `0003_memory.sql`.

## Validation results
- ruff check + format: clean · pyright: 0 errors · pytest: 72 passed · integration: 3 passed (incl. `PgMemoryStore`) · `scripts/smoke.sh` local: SMOKE OK · live `/chat` SSE: status → token → done
- Live run (real Claude, stub search, in-memory memory): CHF briefing → answer; follow-up "which are Phase 3?" → answer citing emerging_treatments chunks; dosing question → refuse; weather → refuse; "Asthma briefing for my patient John Smith" → redact with briefing.

## Deviations from the plan
- `MemoryStore.save_briefing` / `last_briefing` return a `Briefing` dataclass instead of raw `add_turn(role="retrieved")` calls — same storage, typed API.
- The B stub reads `corpus/condition-briefing/` (all 10 conditions, real labels) instead of hardcoded fixtures, so live runs work before merge. Not in the Docker image → stub returns nothing there (refuse `no_evidence`); irrelevant after merge.
- Refusals emit the refusal text as one `token` event, so the UI has one render path; `done` stays authoritative.
- `pyproject.toml` ruff isort `known-first-party` gains the new packages.

## Issues encountered
- **Latency over budget:** live answerable briefings took 17–21 s (planner 6–10 s, answerer 9–12 s, critic ~1.6 s), vs 6.5–8 s in the dry run; no retries were involved. Refusals were 2.2 s. Likely the larger evidence set (13 chunks vs 7) and API latency today; re-measure after merge with real search before tuning (e.g. effort, k, or planner short-circuit on a code alias match).
- `PgMemoryStore` round trip passes against the shared Supabase (memory tables already applied there).

### Needs for merge
- Swap stubs in `api/agents/deps.py` for `rag.search.search` and `rag.conditions.list_conditions`.
- Pane B: `0003_memory.sql` per T2 shape (follow-up evidence is stored as `turns` with `role='retrieved'`, JSON content — no extra column needed). PII golden case must be a briefing request with a name, not advice.
- Pane C: `AskResponse.session_id` (keep it for follow-ups), `/chat` `error` event `{"detail": cls}`, `GET /recent` → `{"user_id", "conditions": [{"condition_id", "name", "viewed_at"}]}`.

## Amendment 2026-10-08 — merge prep with pane B
- Merged `pane-b` into `pane-a` (no overlapping files). Applied B's needs from A: `uv add voyageai pyyaml`,
  `"rag"` in isort `known-first-party` (settings were already in `config.py`).
- `api/schemas/` re-exports `RetrievedChunk`, `Condition`, `Section`, `SECTIONS` from `rag.models`: Pydantic rejects
  a look-alike class, so `AskResponse(retrieved=<rag chunks>)` would have failed with two definitions.
- `agents/deps.py`: stubs removed; real `rag.search` (EmbeddingError → `RetrievalError`, a `PipelineError` → 503) and
  `rag.list_conditions`.
- Golden set first run 12/14: (1) the harness picks its own session ids and `ensure_session` replaced unknown ids →
  now creates the session under the client's id unless another user owns it; (2) the planner refused
  "Brief me on COPD for my patient [REDACTED-NAME]" as clinical advice → prompt now says a patient mention alone is
  still a briefing. Re-run: **14/14 PASS**, every metric 1.00 (`evals/results/20261008-113405-condition-briefing.json`).
- Latency with real search: answerable 11–13 s, refusal 3 s (budget 6.5–8 s) — still over; next lever is the
  answerer (effort/k) and skipping the planner LLM call when the code alias match is unambiguous.
- Validation: ruff/format/pyright clean · api unit 83 · integration 4 (incl. B's ingest/search) · evals checks + fake
  harness PASS · local smoke OK.
