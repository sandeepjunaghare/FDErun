# Feature: Condition briefing pipeline — planner → retriever → answerer → critic, `/ask` + `/chat` + `/recent`

Validate documentation and codebase patterns before you start. Mirror names exactly: `AskResponse`,
`RetrievedChunk`, `Section` are fixed by the interface notes and `evals/contract.py`.

## Feature Description

A strategist sends a condition name (or a follow-up question). The pipeline either refuses (out of scope, unknown
condition, clinical/patient-specific advice) or returns a three-section markdown briefing in which every claim cites
retrieved chunk ids that carry a source label and an as-of date. Guardrails run in code on typed models. Session
memory serves follow-ups; persistent memory keeps each user's recent conditions.

## User Story

As a health-system strategist
I want to type a condition and get a sourced, dated three-section briefing (or a clear refusal)
So that I can trust and reuse it without checking every claim by hand

## Problem Statement

`api/` has health routes only. There is no `/ask` for the evals, no `/chat` for the UI, no agents, guardrails or
memory. Pane B (search, conditions, migrations) and pane C (UI) code against interfaces this ticket must serve.

## Solution Statement

- **Structured, not parsed, output.** The answerer returns a typed `BriefingDraft` (three section lists of
  `Claim{text, chunk_ids}`); code renders the markdown with the three fixed headings and `[chunk-id]` markers. So
  "exactly three headings" and section integrity are checked on data, not regex over markdown.
- **Dependency injection.** `Pipeline(deps: PipelineDeps)` takes `llm`, `search`, `list_conditions`, `memory`.
  Tests pass fakes; `main.py` wires real ones. Pane B's `rag.search` / `rag.conditions` don't exist on this branch,
  so `agents/deps.py` holds **stubs** (fixture conditions + canned chunks, flagged with a log warning) until merge;
  the swap is a two-line import change, written as a task for the merge step.
- **One async generator** `pipeline.run(req)` yields events (`status`, `token`, `done`). `/chat` serialises them as
  SSE with `StreamingResponse` (no new SSE library — project rule: no untested library). `/ask` drains the same
  generator and returns the `done` payload. Tokens are emitted only after the critic passes.
- **Order:** PII redaction (code, on input) → planner (haiku) → code condition check → retriever (3 × `search`,
  `asyncio.gather`) → answerer (sonnet) → critic (code checks, then haiku faithfulness) → retry answerer once with
  the critic's reasons → refuse. Memory writes happen last, on redacted text only.

## Out of Scope / Non-Goals

- Not included: migrations (pane B writes `0003_memory.sql` to the shape in T2), `rag/` search and ingest (pane B),
  UI (pane C), README/deploy (pane D), golden set (pane B).
- Not included: Langfuse tracing in the API (evals already trace); keyword/hybrid search (deferred by architecture).
- Not changing: `/health`, `/version`, `/health/db`, `/smoke`, `db/` helpers, `Settings.database_url` validation.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High (~1300 lines incl. tests)
**Primary Systems Affected**: `api/agents/`, `api/schemas/`, `api/guardrails/`, `api/memory/`, `api/main.py`, `api/config.py`
**Dependencies**: `anthropic>=1.11` (already used and verified in `evals/`)

## Related Work

**Implements**: `docs/tickets/condition-briefing.md#T1` · **Epic**: `docs/condition-briefing.prd.md` + `docs/architecture.md`

**Back-references**: dry-run `/ask` (deleted; lessons in `docs/runbook-kickoff.md` → Dry-run lessons) — LLM helper,
models, critic order, timings.

**Forward-references**: T2 (pane B) supplies `rag.search`, `rag.conditions`, memory tables; T3 (pane C) consumes
`/chat`, `/recent`.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `docs/tickets/condition-briefing.md` (Interface notes 1–7, T1) — Why: the seams; names are fixed.
- `docs/architecture.md` (lines 25–72) — Why: approach, guardrails, memory, output contract (inherited, not re-decided).
- `docs/runbook-kickoff.md` (lines 174–207) — Why: LLM helper shape, models, effort/fallback flags, timings, sandbox + ruff gotchas.
- `evals/contract.py` — Why: `AskResponse` / `RetrievedChunk` / `Action` to mirror in `api/schemas/` (api can't import evals; separate uv project).
- `evals/README.md` (lines 37–62) — Why: `/ask` + SSE event contract.
- `evals/judge.py` (lines 44–83) — Why: the `messages.parse(output_format=…)` call + error mapping to mirror in `agents/llm.py`.
- `api/main.py` (lines 40–51) — Why: route style; 503 with `type(e).__name__` only, full error to `log.warning`.
- `api/config.py` — Why: add settings with empty defaults; `get_settings()` is the only env access.
- `api/tests/test_health.py` (lines 10–24) — Why: test-client pattern without lifespan, `monkeypatch.setattr(main, …)` stubs.
- `corpus/condition-briefing/heart-failure/*.md` — Why: realistic chunk text, aliases (`CHF`), labels for test fixtures and the stub.

### New Files to Create

- `api/schemas/__init__.py` — re-exports.
- `api/schemas/contract.py` — `Section`, `Action`, `AskRequest`, `RetrievedChunk` (+ optional `section`, `source_label`, `as_of`), `AskResponse`, `Condition`.
- `api/schemas/agents.py` — `PlannerOutput`, `Claim`, `BriefingDraft`, `CriticVerdict`, `RecentCondition`, `RecentResponse`.
- `api/agents/__init__.py`
- `api/agents/llm.py` — shared `LLM` protocol + `ClaudeLLM`, `LLMError`, `LLMRefusal`.
- `api/agents/planner.py`, `retriever.py`, `answerer.py`, `critic.py`, `pipeline.py`, `deps.py` (wiring + B stubs), `render.py` (markdown + token chunks).
- `api/guardrails/__init__.py`, `pii.py`, `scope.py`, `citations.py` (citation check + section integrity).
- `api/memory/__init__.py`, `store.py` (`MemoryStore` protocol, `PgMemoryStore`, `InMemoryStore` for tests).
- `api/tests/fakes.py` — `FakeLLM` (scripted responses per agent), `fake_search`, `fake_conditions`, chunk fixtures.
- `api/tests/test_guardrails.py`, `test_pipeline.py`, `test_routes.py`, `test_memory.py`.

### Relevant Documentation

- Anthropic Python SDK structured output — same call already working in `evals/judge.py`; no external research needed.
- FastAPI `StreamingResponse` (`media_type="text/event-stream"`) — standard, already a dependency.

### Patterns to Follow

**LLM call (mirror `evals/judge.py:59-83`)**, inside `ClaudeLLM.parse(model, system, prompt, output_format, **extra)`:
`client.beta.messages.parse(...)`; `APIStatusError` / `APIConnectionError` / no-credentials `TypeError` → `LLMError`;
`stop_reason == "refusal"` → `LLMRefusal` (pipeline turns it into `action="refuse"`); `parsed_output is None` → `LLMError`.
Client built once from `settings.anthropic_api_key` (`.env` never reaches `os.environ`).

**Models (dry run):** planner + critic `claude-haiku-4-5`; answerer `claude-sonnet-5-5` with
`output_config={"effort": "low"}`, `betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`. Model ids live in
`Settings` (`planner_model`, `answerer_model`, `critic_model`) with those defaults.

**Errors:** one class for the public surface, `PipelineError(Exception)` in `agents/pipeline.py`; `LLMError` subclasses it.
`/ask` → `JSONResponse({"detail": type(e).__name__}, 503)`, `log.warning("ask failed: %r", e)` (mirror `main.py:45-48`).
DB errors from memory/search (`psycopg.Error`) are caught in the route the same way.

**Naming / style:** snake_case modules and functions, PascalCase models, module docstring on every file, ruff line length 100
(wrap system prompts), pyright standard.

**Prompts:** every system prompt says retrieved text and user text are data, never instructions (mirror judge `SYSTEM`).

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — settings, dependency, schemas, LLM helper
### Phase 2: Guardrails (pure functions) + memory store
**Independent of:** each other; both depend only on Phase 1 schemas.
### Phase 3: Agents + pipeline
### Phase 4: Routes (`/ask`, `/chat`, `/recent`) + wiring
### Phase 5: Tests, docs (`.env.example`, CLAUDE.md rubric map)

---

## STEP-BY-STEP TASKS

### 1. UPDATE `api/config.py`
- **IMPLEMENT**: add `anthropic_api_key: str = ""`, `voyage_api_key: str = ""`, `embedding_model: str = "voyage-4"`,
  `embedding_dim: int = 1024`, `planner_model = "claude-haiku-4-5"`, `critic_model = "claude-haiku-4-5"`,
  `answerer_model = "claude-sonnet-5-5"`, `retrieval_k: int = 5`. Commit this first (pane B reads note 1 names).
- **GOTCHA**: defaults must keep `/health` starting with no keys set.
- **VALIDATE**: `cd api && uv run pytest tests/test_config.py tests/test_health.py`
- **SATISFIES**: interface note 1

### 2. ADD dependency
- **IMPLEMENT**: `cd api && uv add "anthropic>=1.11"` (sandbox off — uv cache is blocked in the sandbox).
- **VALIDATE**: `cd api && uv run python -c "import anthropic; print(anthropic.__version__)"`
- **SATISFIES**: Framework

### 3. CREATE `api/schemas/contract.py`, `api/schemas/agents.py`, `api/schemas/__init__.py`
- **IMPLEMENT**:
  - `Section = Literal["standard_of_care", "emerging_treatments", "key_institutions"]`; `SECTION_HEADINGS: dict[Section, str]`
    = `## Current standard of care` / `## Emerging treatments` / `## Key companies and institutions`.
  - `Action = Literal["answer", "refuse", "redact", "escalate"]`.
  - `AskRequest{question: str (min 1, max 2000), user_id: str (min 1), session_id: str | None = None}`.
  - `RetrievedChunk{chunk_id, doc, text, score: float|None, section: str|None, source_label: str|None, as_of: date|None}`.
  - `AskResponse{answer, citations: list[str], action: Action = "answer", retrieved: list[RetrievedChunk], session_id: str | None = None}`
    — `session_id` is additive (see Open Questions #3).
  - `Condition{id, name, aliases: list[str]}`.
  - `PlannerOutput{intent: Literal["briefing","follow_up","out_of_scope"], condition_id: str|None, refuse_reason: Literal["unrelated","clinical_advice","unknown_condition"]|None, rationale: str}`.
  - `Claim{text: str, chunk_ids: list[str]}`; `BriefingDraft{standard_of_care: list[Claim], emerging_treatments: list[Claim], key_institutions: list[Claim]}`
    (follow-up drafts use `FollowUpDraft{claims: list[Claim]}`).
  - `CriticVerdict{faithful: bool, unsupported_claims: list[str]}`.
  - `RecentCondition{condition_id, name, viewed_at: datetime}`; `RecentResponse{user_id, conditions: list[RecentCondition]}`.
- **GOTCHA**: field names in `RetrievedChunk`/`AskResponse` must equal `evals/contract.py` (plus note 4 fields).
- **VALIDATE**: `cd api && uv run pyright schemas`
- **SATISFIES**: notes 4, 7; guardrails "on typed models"

### 4. CREATE `api/agents/llm.py`
- **IMPLEMENT**: `class LLM(Protocol): async def parse[T: BaseModel](self, *, model, system, prompt, output_format: type[T], **extra) -> T`;
  `ClaudeLLM(settings)` per pattern above; `LLMError(PipelineError)`, `LLMRefusal(Exception)`. `max_tokens` 1024 planner/critic, 4000 answerer (param).
- **PATTERN**: `evals/judge.py:59-83`
- **GOTCHA**: `PipelineError` lives in `agents/errors.py` to avoid a circular import between `llm.py` and `pipeline.py`.
- **VALIDATE**: `cd api && uv run pyright agents`
- **SATISFIES**: "one specific exception class"

### 5. CREATE `api/guardrails/pii.py`
- **IMPLEMENT**: `redact(text) -> tuple[str, list[str]]` (redacted text, kinds found). Regexes: email, phone, SSN
  (`\d{3}-\d{2}-\d{4}`), MRN (`MRN[:#\s]*\w+`), dates of birth (`DOB` / `born on` + date), and patient-name patterns:
  `(patient|pt\.?|Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)?` and `named [A-Z][a-z]+ [A-Z][a-z]+`. Replaces with `[REDACTED-<KIND>]`.
- **GOTCHA**: must not redact condition names/aliases (`CHF`, `COPD` are all-caps → name regex requires Capital+lowercase). Test each corpus alias is untouched.
- **VALIDATE**: `cd api && uv run pytest tests/test_guardrails.py -k pii`
- **SATISFIES**: PII redaction on input

### 6. CREATE `api/guardrails/scope.py`
- **IMPLEMENT**: `match_condition(text, conditions) -> Condition | None` — case-insensitive word-boundary match on name +
  aliases (longest first), used as a code hint to the planner and as a fallback check; `check_scope(plan, conditions) -> RefuseReason | None`
  — refuse if `intent == "out_of_scope"`, or `briefing` with `condition_id` not in the list (LLM can't invent an id).
- **VALIDATE**: `cd api && uv run pytest tests/test_guardrails.py -k scope`
- **SATISFIES**: scope guardrail; "CHF" → heart failure

### 7. CREATE `api/guardrails/citations.py`
- **IMPLEMENT**: `check_draft(draft, retrieved) -> list[str]` (problems; empty = pass): every claim has ≥1 chunk id; every id ∈ retrieved;
  **section integrity**: a claim under section S cites only chunks whose `section == S`; every section has ≥1 claim. For `FollowUpDraft`: non-empty + ⊆ retrieved only.
- **VALIDATE**: `cd api && uv run pytest tests/test_guardrails.py -k citations`
- **SATISFIES**: citation check, section-integrity domain rule

### 8. CREATE `api/memory/store.py`
- **IMPLEMENT**: `MemoryStore` protocol: `ensure_session(session_id|None, user_id) -> str` (new uuid4 if None; reject a
  session owned by another user → new session), `add_turn(session_id, role, content, citations)`,
  `last_briefing(session_id) -> (condition_id, list[RetrievedChunk]) | None`, `touch_recent(user_id, condition_id)`,
  `recent(user_id, limit=10) -> list[(condition_id, viewed_at)]` newest first. `PgMemoryStore(pool)` with SQL against
  `sessions`, `turns`, `recent_conditions` (T2 shape; `on conflict (user_id, condition_id) do update set viewed_at = now()`).
  The briefing's evidence is saved as a turn with `role="retrieved"`, `content` = JSON `{"condition_id", "chunks": [...]}`,
  `citations` = chunk ids. `InMemoryStore` with the same behaviour for unit tests.
- **GOTCHA**: only redacted text is ever passed in. All queries parameterised. Tables don't exist until B's migration
  runs → integration test only.
- **VALIDATE**: `cd api && uv run pytest tests/test_memory.py`
- **SATISFIES**: session + persistent memory

### 9. CREATE `api/agents/planner.py`
- **IMPLEMENT**: `async def plan(llm, settings, question, conditions, has_session_briefing, hint) -> PlannerOutput`. System prompt: three intents;
  refuse clinical / patient-specific treatment advice, other topics; choose `condition_id` only from the supplied list; `follow_up` only if a briefing exists.
  `LLMRefusal` → `PlannerOutput(intent="out_of_scope", refuse_reason="clinical_advice")`.
- **VALIDATE**: `cd api && uv run pytest tests/test_pipeline.py -k planner`
- **SATISFIES**: planner AC

### 10. CREATE `api/agents/retriever.py`
- **IMPLEMENT**: plain `async def retrieve(search, pool, query, condition_id, k) -> list[RetrievedChunk]`; `asyncio.gather` of three `search` calls (one per section), concatenated in section order, dedup by `chunk_id`.
- **VALIDATE**: `cd api && uv run pytest tests/test_pipeline.py -k retriev`
- **SATISFIES**: retriever AC (a function, not an agent)

### 11. CREATE `api/agents/answerer.py` + `api/agents/render.py`
- **IMPLEMENT**: `draft_briefing(llm, settings, condition, chunks, feedback: list[str] | None) -> BriefingDraft`; passages rendered as
  `<passage id=… section=… source=… as_of=…>`; feedback from the critic appended on retry. `draft_follow_up(…, question, chunks) -> FollowUpDraft`.
  `render.py`: `to_markdown(draft) -> str` (three headings, bullets, ` [id1, id2]` markers), `citations_of(draft)` (ordered unique), `token_chunks(md)` (split by line).
- **VALIDATE**: `cd api && uv run pytest tests/test_pipeline.py -k render`
- **SATISFIES**: answerer AC (exact headings, every claim cites)

### 12. CREATE `api/agents/critic.py`
- **IMPLEMENT**: `async def review(llm, settings, question, draft, retrieved) -> list[str]` — `check_draft` first; if problems, return them without the LLM call; else haiku
  faithfulness on the rendered markdown vs cited passages → `CriticVerdict`; unsupported claims become problems.
- **VALIDATE**: `cd api && uv run pytest tests/test_pipeline.py -k critic`
- **SATISFIES**: critic AC (code first, then LLM)

### 13. CREATE `api/agents/pipeline.py` + `api/agents/errors.py`
- **IMPLEMENT**: `PipelineDeps` dataclass (`llm`, `search`, `list_conditions`, `memory`, `pool`, `settings`). `async def run(req, deps) -> AsyncIterator[Event]`,
  `Event = tuple[Literal["status","token","done"], dict]`. Flow: redact → `ensure_session` → yield status planner → plan → (refuse → done) → follow-up:
  `last_briefing` evidence, draft_follow_up → else status retriever → retrieve (empty → refuse) → status answerer → draft → status critic → review →
  problems → one retry with feedback → still problems → refuse. Pass → `token` events, then `done`. `action = "redact"` if PII fired and the answer
  passed; refusals stay `"refuse"`. Memory: user turn (redacted), retrieved turn, assistant turn, `touch_recent`. Refusal answers are fixed,
  short, user-facing strings per reason (no LLM text). `async def ask(req, deps) -> AskResponse` drains `run`.
- **GOTCHA**: never yield `token` before the critic passes; refusals emit no tokens? — emit the refusal text as one token so the UI has one render path (done is authoritative either way).
- **VALIDATE**: `cd api && uv run pytest tests/test_pipeline.py`
- **SATISFIES**: pipeline, retry-then-refuse, note 5

### 14. CREATE `api/agents/deps.py`
- **IMPLEMENT**: `build_deps(app_state, settings) -> PipelineDeps`. Until pane B merges: `stub_search` / `stub_list_conditions`
  returning corpus-shaped fixtures for heart failure (log `warning` once: "rag stubs in use"). **Merge task:** replace with
  `from rag.search import search` and `from rag.conditions import list_conditions`.
- **VALIDATE**: `cd api && uv run pyright agents`
- **SATISFIES**: works before T2 merges

### 15. UPDATE `api/main.py`
- **IMPLEMENT**: lifespan also builds `app.state.deps` (LLM client lazily — no key needed for health routes).
  `POST /ask` → `AskResponse` (503 `{"detail": cls}` on `PipelineError` / `psycopg.Error`).
  `POST /chat` → `StreamingResponse(media_type="text/event-stream")`, frames `event: <name>\ndata: <json>\n\n`; on error emits
  `event: error` `data: {"detail": cls}` and closes. `GET /recent?user_id=` → `RecentResponse` (names joined from `list_conditions`).
- **PATTERN**: `main.py:40-51`
- **VALIDATE**: `cd api && uv run pytest tests/test_routes.py tests/test_health.py`
- **SATISFIES**: `/ask`, `/chat`, `/recent` ACs

### 16. CREATE tests: `api/tests/fakes.py`, `test_guardrails.py`, `test_memory.py`, `test_pipeline.py`, `test_routes.py`
- **IMPLEMENT**: `FakeLLM` returns scripted outputs keyed by `output_format` (queue per type), records calls. Cases:
  refusals (weather; unknown condition; "what dose should my patient take" → refuse, **zero** `search` calls);
  alias "CHF" → `heart-failure`; happy path (three headings, citations ⊆ retrieved, as_of/source_label present);
  section-integrity rejection → retry → pass; retry-then-refuse (two bad drafts → `refuse`, no `token` events);
  faithfulness failure → retry; follow-up uses stored chunks and calls `search` zero times; PII (`patient John Smith` →
  redacted before the planner sees it, `action="redact"`, stored turn redacted); `LLMError` → `/ask` 503 with `{"detail": "LLMError"}`;
  `/chat` event order `status…, token…, done`; `/recent` newest first. `@pytest.mark.integration` round trip for `PgMemoryStore`.
- **VALIDATE**: `cd api && uv run pytest`
- **SATISFIES**: unit-test AC

### 17. UPDATE `.env.example`, `CLAUDE.md`
- **IMPLEMENT**: `.env.example`: model overrides commented (`# PLANNER_MODEL=claude-haiku-4-5` etc.), no values for secrets.
  `CLAUDE.md`: rubric rows Multi-agent orchestration / Memory / Guardrails / Framework → "built (unit-tested, stub search)"; map `api/agents/deps.py`, `/recent`.
- **VALIDATE**: gitleaks command from CLAUDE.md
- **SATISFIES**: ground rules

---

## TESTING STRATEGY

Unit (offline, default `pytest`): LLM, `search`, `list_conditions` and memory all faked via `PipelineDeps`; routes via
`TestClient` without lifespan (`main.app.state.deps = …`). Integration (`-m integration`): `PgMemoryStore` against Supabase once
B's `0003_memory.sql` exists; skip with a clear reason if the tables are missing.

Edge cases: empty question (422); session id owned by another user; follow-up with no prior briefing → planner sees
`has_session_briefing=False` → treated as briefing/refuse; search returns nothing for a section → critic flags empty
section → retry → refuse; LLM refusal stop reason; duplicate chunk ids across sections; alias that's a substring of a word (`HF` in `HFpEF`).

## VALIDATION COMMANDS

1. `cd api && uv run ruff check . && uv run ruff format --check . && uv run pyright`
2. `cd api && uv run pytest`
3. `cd api && uv run pytest -m integration` (after T2's migration is applied; memory tables)
4. Manual: `uv run uvicorn main:app --port 8710`, then
   `curl -s localhost:8710/ask -H 'content-type: application/json' -d '{"question":"CHF","user_id":"u1"}'` (stub search, real Claude) and
   `curl -N localhost:8710/chat …` to see `status`/`token`/`done`; `curl 'localhost:8710/recent?user_id=u1'`.
5. Optional: `cd evals && uv run python run.py golden/example.yaml --target fake` still green (contract untouched).

## ACCEPTANCE CRITERIA

- [ ] `/ask` returns `AskResponse`; `/chat` streams `status` → `token` (post-critic only) → `done` with the same payload
- [ ] Planner refuses unrelated, unknown-condition and clinical-advice questions before retrieval; "CHF" resolves to heart failure
- [ ] Retriever is a function making three section-filtered `search` calls
- [ ] Briefing has exactly the three headings; every claim cites retrieved ids
- [ ] Critic: code checks (non-empty, ⊆ retrieved, section integrity) then LLM; one retry, then refuse
- [ ] PII redacted before planner, storage; `action="redact"`
- [ ] Follow-ups answer from the session's stored chunks, cited; `/recent` newest first
- [ ] One `PipelineError` class; `/ask` 503 names the class only
- [ ] ruff, pyright, pytest clean

## OPEN QUESTIONS / ASSUMPTIONS

1. **Follow-up evidence storage.** T2's `turns` table has no column for retrieved chunks. Assumption: store them as a turn with
   `role="retrieved"` and JSON `content` — no schema change needed. Alternative: ask B for a `jsonb` column.
2. **PII vs refusal precedence.** Assumption: refuse beats redact; a briefing request with a patient name is answered with
   `action="redact"`. Pane B's `pii` golden case must be a non-advice question (e.g. "Briefing on CHF for my patient John Smith").
3. **Additive fields for pane C:** `AskResponse.session_id` (so the UI can keep the session on the first turn), the `/chat` `error`
   event, and `RecentResponse` shape. Need to be told to panes B (contract mirror) and C.
4. **PII name detection is regex-only** (titles / "patient X Y" patterns); a bare name without a cue word won't be caught. No NER library (untested).
5. Stubs: `rag.search` / `rag.conditions` stubbed in `agents/deps.py`; merge step swaps the imports.

## NOTES

Why structured drafts instead of free markdown: section integrity and "every claim cites" become set checks on typed data,
which is what "guardrails in code, not prompts" means here; the markdown the user sees is generated from the checked draft,
so what was checked is exactly what is shown.

Latency budget (dry run): 6.5–8 s answerable; a retry adds ~3–5 s; refusal 1–2 s.

## AMENDMENTS
