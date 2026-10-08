# Feature: Condition-briefing retrieval — schema, ingest, search, golden set (pane B, T2)

The following plan should be complete, but validate documentation and codebase patterns and task sanity before
you start implementing. Import from the right files (`config.get_settings`, `contract.RetrievedChunk`, …).

## Feature Description

Make the labeled synthetic corpus (`corpus/condition-briefing/`, 10 conditions × 3 sections) searchable by
condition and section in Supabase pgvector, expose `search` and `list_conditions` for pane A's retriever and
planner, create the memory tables pane A's `api/memory/` will use, extend the eval contract with source labels
and dates, and write the golden set that judges the briefing.

## User Story

As a health-system strategist
I want every section of my briefing to draw only on sources labeled for that condition and section, with their label and date
So that I can trust where each claim comes from and how fresh it is

## Problem Statement

Today the DB holds only `smoke_checks`; there is no documents/chunks schema, no ingest, no search, and the eval
set covers a fake benefits corpus. Panes A and C are coding against interface notes 2–4 and 6 that don't exist yet.

## Solution Statement

Two numbered migrations (corpus tables; memory tables). An offline `python -m rag.ingest <corpus-dir>` that
validates the corpus with `scripts/check_corpus.py`'s own `check()`, chunks each document by paragraph with stable
ids, embeds with Voyage (`input_type="document"`), and upserts. `rag.search` embeds the query
(`input_type="query"`) and runs one filtered cosine query. `rag.conditions.list_conditions` reads the conditions
table. `evals/contract.py` gains the three optional fields; the golden set adds 12–13 cases, including a two-turn
follow-up, which needs a small, opt-in session feature in the eval harness.

## Out of Scope / Non-Goals

- Not included: hybrid/keyword search (architecture defers it), reranking, any agent/planner logic (pane A).
- Not included: code that reads/writes memory tables (`api/memory/`, pane A) — only their DDL.
- Not changing: `api/config.py`, `api/pyproject.toml`, `api/uv.lock`, `.env.example`, `api/main.py` (pane A); see
  "Needs from A".
- Not changing: `scripts/check_corpus.py` (imported read-only), the existing eval metrics and `example.yaml`.
- No `/ingest` route: ingest runs once from a laptop (CLAUDE.md → Commands).

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `api/db/migrations/`, `api/rag/` (new), `api/tests/test_rag*.py`, `evals/`
**Dependencies**: `voyageai` (verified in dry run), `pyyaml`, psycopg 3 async, pgvector extension (already on)

## Related Work

**Implements**: `docs/tickets/condition-briefing.md#T2` · **Epic**: `docs/condition-briefing.prd.md`,
`docs/architecture.md` (Data model, Retrieval — inherited, not reopened)

**Back-references**: dry-run patterns in `docs/runbook-kickoff.md` → Dry-run lessons (ingest/search SQL, Voyage
import path, settings names).

**Forward-references**: T1 (pane A) swaps its stubs for `rag.search` / `rag.conditions`; T3 reads the new
`RetrievedChunk` fields.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `docs/tickets/condition-briefing.md` (interface notes 1–4, 6; T2) — the exact signatures and table shapes.
- `api/db/migrations/0001_smoke.sql` — migration style: `create table if not exists`, comment, RLS line.
- `api/db/migrate.py` — one transaction per file; files applied in name order, once.
- `api/db/__init__.py` (lines 35–62) — async pool usage and `%s::vector` with a `"[…]"` string literal (no
  pgvector adapter registration needed).
- `api/config.py` — `get_settings()`; fields `voyage_api_key`, `embedding_model`, `embedding_dim` are added by
  pane A (note 1). Not present on this branch yet.
- `scripts/check_corpus.py` — `check(root) -> list[str]`, `front_matter(path)`, `SECTIONS`.
- `scripts/check_embeddings.py` (lines 50–60) — Voyage embed call shape (`output_dimension`, `input_type`).
- `corpus/condition-briefing/README.md` + any `*/standard_of_care.md` — front matter fields, paragraph-per-claim.
- `api/tests/test_health.py` — monkeypatch stub style; `api/pyproject.toml` — pytest marker `integration`.
- `evals/contract.py`, `evals/metrics.py` (19–33: hit = `doc ==` and `contains in text`), `evals/run.py`
  (59–118: `evaluate`), `evals/targets.py` (Target protocol, HttpTarget, FakeTarget), `evals/tests/`.

### New Files to Create

- `api/db/migrations/0002_condition_briefing.sql`
- `api/db/migrations/0003_memory.sql`
- `api/rag/__init__.py` — re-exports `Section`, `Condition`, `search`, `list_conditions`
- `api/rag/models.py` — `Section` Literal, `Condition`, `RetrievedChunk` (mirrors `evals/contract.py` names), `Chunk`
- `api/rag/corpus.py` — load + validate corpus, parse front matter, chunk by paragraph (pure, offline)
- `api/rag/embed.py` — Voyage async client wrapper; `EmbeddingError`
- `api/rag/ingest.py` — `python -m rag.ingest <corpus-dir>` (+ `__main__` guard)
- `api/rag/search.py`, `api/rag/conditions.py`
- `api/tests/test_rag_corpus.py` (offline), `api/tests/test_rag_search.py` (offline, stubbed embed + fake conn),
  `api/tests/test_rag_integration.py` (`@pytest.mark.integration`)
- `evals/golden/condition-briefing.yaml`

### Relevant Documentation

- Voyage: `voyageai.client_async.AsyncClient(api_key=…).embed(texts, model=, input_type=, output_dimension=)` —
  already verified in the dry run; no new research needed.
- pgvector HNSW: `create index … using hnsw (embedding vector_cosine_ops)`.

### Patterns to Follow

- **SQL**: lowercase keywords, `create … if not exists`, a one-line comment per table, then
  `alter table <t> enable row level security;` (no policies) — `0001_smoke.sql`.
- **Vectors**: pass as `"[" + ",".join(map(str, v)) + "]"` with `%s::vector` — `db/__init__.py:46`.
- **Score**: `1 - (embedding <=> %s::vector) as score … order by embedding <=> %s::vector limit %s` (dry run).
- **Errors**: one specific exception per failure kind (`CorpusError`, `EmbeddingError`); message names the
  problem, never secrets.
- **Docstrings**: one-line purpose plus raises, as in `db/__init__.py`. Line length 100.
- **Tests**: plain pytest functions, `monkeypatch` stubs; anything touching Supabase/Voyage → `integration`.

---

## IMPLEMENTATION PLAN

### Phase 1: Schema (migrations)
### Phase 2: Corpus parsing + chunking (pure, offline-tested)
### Phase 3: Embedding, ingest, search, conditions
**Depends on:** Phase 1 (tables), Phase 2 (chunks); "Needs from A" settings + deps to type-check/run.
### Phase 4: Evals contract + harness session + golden set
**Independent of:** Phases 1–3 (only `evals/`). Can go first if Needs-from-A is late.

---

## STEP-BY-STEP TASKS

### CREATE `api/db/migrations/0002_condition_briefing.sql`

- **IMPLEMENT**:
  - `conditions(id text primary key, name text not null, aliases text[] not null default '{}')`
  - `documents(doc text primary key, condition_id text not null references conditions(id), section text not null
    check (section in ('standard_of_care','emerging_treatments','key_institutions')), title text not null,
    source_label text not null, source_type text not null, as_of date not null)`
  - `chunks(chunk_id text primary key, doc text not null references documents(doc) on delete cascade, ord int not
    null, condition_id text not null, section text not null, text text not null, embedding vector(1024) not null,
    unique (doc, ord))`
  - `create index if not exists chunks_embedding_hnsw on chunks using hnsw (embedding vector_cosine_ops);`
  - `create index if not exists chunks_condition_section on chunks (condition_id, section);`
  - RLS enabled on all three.
- **GOTCHA**: `vector(1024)` is hard-coded (must equal `EMBEDDING_DIM`); ingest asserts the dim before writing.
  Never edit after it's applied — new file instead.
- **VALIDATE**: `cd api && uv run python -m db.migrate` (sandbox off) → `applied 0002_condition_briefing.sql`
- **SATISFIES**: AC 1

### CREATE `api/db/migrations/0003_memory.sql`

- **IMPLEMENT**: `sessions(session_id text pk, user_id text not null, created_at timestamptz not null default
  now())`; `turns(id bigserial pk, session_id text not null references sessions on delete cascade, role text not
  null, content text not null, citations text[] not null default '{}', created_at timestamptz not null default
  now())` + index `(session_id, id)`; `recent_conditions(user_id text not null, condition_id text not null
  references conditions(id), viewed_at timestamptz not null default now(), primary key (user_id, condition_id))`
  + index `(user_id, viewed_at desc)`. RLS on all three.
- **GOTCHA**: `role` left unconstrained (pane A decides values); `turns` has no `user_id` — scoping goes through
  `sessions.user_id`.
- **VALIDATE**: migrate again → `applied 0003_memory.sql`; re-run → `0 applied`.
- **SATISFIES**: AC 2

### CREATE `api/rag/models.py`

- **IMPLEMENT**: `Section = Literal["standard_of_care","emerging_treatments","key_institutions"]`;
  `SECTIONS: tuple[Section, ...]`; Pydantic `Condition(id, name, aliases: list[str])`;
  `RetrievedChunk(chunk_id, doc, text, score: float | None, section: str | None, source_label: str | None,
  as_of: date | None)` — same names/types as `evals/contract.py` (note 4; api can't import from evals/);
  `Chunk(chunk_id, doc, ord, condition_id, section, text)` and `Document(doc, condition_id, condition_name,
  aliases, section, title, source_label, source_type, as_of, chunks)`.
- **VALIDATE**: `cd api && uv run pyright rag`
- **SATISFIES**: AC 4

### CREATE `api/rag/corpus.py`

- **IMPLEMENT**:
  - `class CorpusError(Exception)` — carries the list of problems.
  - `validate(root: Path) -> None`: load `scripts/check_corpus.py` via `importlib.util.spec_from_file_location`
    (path `Path(__file__).resolve().parents[2] / "scripts" / "check_corpus.py"`), call `check(root)`; non-empty →
    raise `CorpusError(errors)`. Single source of truth for label rules (ticket: "runs check_corpus.py logic").
  - `parse_document(path: Path, root: Path) -> Document`: split `---\n` front matter (yaml.safe_load), condition
    slug = parent folder name, `doc = f"{slug}/{path.name}"`.
  - `chunk_paragraphs(body: str) -> list[str]`: split on blank lines (`re.split(r"\n\s*\n", …)`), join each
    paragraph's wrapped lines with single spaces, drop empties.
  - `chunk_id = f"{slug}-{section}-{ord}"`, `ord` from 0. Chunk carries `condition_id=slug`, `section`.
  - `load_corpus(root) -> list[Document]`: `validate(root)` then parse `*/*.md` sorted (skip `README.md`).
- **GOTCHA**: `scripts/` isn't in the Docker image — fine, ingest is local-only; raise a clear `CorpusError` if
  the file is missing. `yaml` returns `datetime.date` for `as_of` already.
- **VALIDATE**: `cd api && uv run pytest tests/test_rag_corpus.py`
- **SATISFIES**: AC 3

### CREATE `api/rag/embed.py`

- **IMPLEMENT**: `class EmbeddingError(Exception)`; `async def embed(texts: list[str], input_type:
  Literal["document","query"]) -> list[list[float]]` using `from voyageai.client_async import AsyncClient`,
  `AsyncClient(api_key=settings.voyage_api_key)`, `model=settings.embedding_model`,
  `output_dimension=settings.embedding_dim`; batch at 128 texts; wrap `voyageai.error.VoyageError` →
  `EmbeddingError(type name)`; empty key → `EmbeddingError("VOYAGE_API_KEY not set")`; assert each vector has
  `embedding_dim` dims. `to_pgvector(v) -> str` helper.
- **GOTCHA**: key from settings, not `os.environ` (pydantic-settings doesn't export `.env`).
- **VALIDATE**: pyright clean.
- **SATISFIES**: AC 3, 5

### CREATE `api/rag/ingest.py`

- **IMPLEMENT**: `async def ingest(root: Path, conn) -> IngestStats`: `load_corpus` → embed all chunk texts
  (`document`) → in one transaction: upsert conditions (`on conflict (id) do update set name, aliases`), documents
  (`on conflict (doc) do update …`), chunks (`on conflict (chunk_id) do update set text, embedding, ord, …`), then
  `delete from chunks where doc = %s and ord >= %s` per doc (orphans after re-chunking). `main()` parses argv,
  opens `psycopg.AsyncConnection.connect(get_settings().database_url)`, prints
  `ingested N conditions, M documents, K chunks`; `CorpusError` → prints problems, exit 1, nothing written.
  `if __name__ == "__main__": asyncio.run(main())`.
- **GOTCHA**: embed before opening the transaction (no long-held tx while calling Voyage). Use `executemany`.
- **VALIDATE**: `cd api && uv run python -m rag.ingest ../corpus/condition-briefing` twice → same counts;
  `select count(*) from chunks` unchanged on second run.
- **SATISFIES**: AC 3

### CREATE `api/rag/search.py` and `api/rag/conditions.py`

- **IMPLEMENT**: `async def search(pool, query: str, condition_id: str, section: Section, k: int = 5) ->
  list[RetrievedChunk]` — `embed([query], "query")`, then
  `select c.chunk_id, c.doc, c.text, 1 - (c.embedding <=> %s::vector), c.section, d.source_label, d.as_of from
  chunks c join documents d using (doc) where c.condition_id = %s and c.section = %s order by c.embedding <=>
  %s::vector limit %s`. `async def list_conditions(pool) -> list[Condition]` ordered by name.
  `pool` typed `AsyncConnectionPool`.
- **GOTCHA**: unknown section is prevented by the type; unknown condition returns `[]` (planner refuses earlier).
- **VALIDATE**: `uv run pytest tests/test_rag_search.py`
- **SATISFIES**: AC 4

### CREATE `api/rag/__init__.py`, tests

- `test_rag_corpus.py` (offline, tmp_path corpus + the real corpus): paragraph split; chunk ids stable and
  `<slug>-<section>-<ord>`; front matter → Document fields incl. `as_of: date`; bad corpus (missing section file)
  raises `CorpusError`; real corpus loads 30 docs, 10 conditions, every chunk mentions text.
- `test_rag_search.py` (offline): monkeypatch `rag.search.embed`; fake pool/connection capturing SQL params →
  asserts filters passed and rows mapped into `RetrievedChunk` with section/source_label/as_of.
- `test_rag_integration.py` (`integration`): ingest real corpus into the DB, run twice, count unchanged;
  `search(pool, "CHF quadruple therapy", "heart-failure", "standard_of_care")` returns only that condition/section
  with label + date; `list_conditions` returns 10 with aliases containing "CHF".
- **VALIDATE**: `cd api && uv run pytest` and `uv run pytest -m integration`

### UPDATE `evals/contract.py`

- **IMPLEMENT**: `RetrievedChunk` + `section: str | None = None`, `source_label: str | None = None`, `as_of:
  date | None = None`. `GoldenCase` + `session: str | None = None` (cases sharing a value run in file order in one
  session). Docstring: request may carry `session_id`.
- **VALIDATE**: `cd evals && uv run pytest && uv run python run.py golden/example.yaml --target fake`
- **SATISFIES**: AC 5

### UPDATE `evals/targets.py`, `evals/run.py`

- **IMPLEMENT**: `Target.ask(question, user_id, session_id: str | None = None)`; HttpTarget sends `session_id`
  only when set (eval harness's old request shape unchanged); FakeTarget ignores it. In `evaluate`, group cases by
  `session` (None → own group); each group runs sequentially under the semaphore with
  `session_id = f"eval-{run_id}-{session}"` (`run_id` = timestamp, so reruns don't reuse a session).
- **VALIDATE**: new test in `evals/tests/test_run.py`: two cases with the same `session` reach the target in order
  with the same session_id; `uv run pytest`.
- **SATISFIES**: AC 6 (follow-up case is runnable)

### CREATE `evals/golden/condition-briefing.yaml`

- **IMPLEMENT**: `k: 15` (3 sections × 5 — the harness's top-k is over the whole `retrieved` list). Cases:
  ~7 answerable briefings across distinct conditions, each with `expected_sources` per section (`doc:
  <slug>/<section>.md`, `contains:` a distinctive phrase copied from the corpus) and a short reference answer;
  `alias-chf` ("Brief me on CHF"); `followup-phase3` (session `hf`, after a heart-failure briefing: "Which of
  those emerging treatments are in Phase 3?", expected_sources `heart-failure/emerging_treatments.md`);
  `unknown-condition` (e.g. psoriasis, out_of_scope); `weather` (out_of_scope); `patient-advice` (domain_rule →
  refuse); `pii-name` ("Brief me on COPD for my patient John Smith, DOB 1956-03-02", type `pii`, `expect: redact`).
- **GOTCHA**: copy `contains` phrases verbatim from the corpus (lowercase match). Check which conditions are NOT in
  the corpus before choosing the unknown one.
- **VALIDATE**: `cd evals && uv run python -c "from golden import load_golden; print(len(load_golden('golden/condition-briefing.yaml').cases))"`
  and a script check that every `contains` occurs in its doc.
- **SATISFIES**: AC 6

---

## TESTING STRATEGY

- **Unit (offline)**: corpus parse/chunk/validate; search SQL wiring with stubbed embed + fake connection; evals
  session grouping; existing `example.yaml` against fake target.
- **Integration**: ingest + idempotency + search filter + conditions against real Supabase + Voyage.
- **Edge cases**: bad corpus refuses ingest with nothing written; re-run doesn't duplicate; shrinking a doc's
  paragraph count deletes orphan chunks; empty `VOYAGE_API_KEY` → `EmbeddingError`; unknown condition → `[]`.

## VALIDATION COMMANDS

1. `cd api && uv run ruff check . && uv run ruff format --check . && uv run pyright`
2. `cd api && uv run pytest`
3. `cd api && uv run python -m db.migrate && uv run python -m rag.ingest ../corpus/condition-briefing` (×2) and
   `uv run pytest -m integration`
4. `cd evals && uv run ruff check . && uv run pyright && uv run pytest && uv run python run.py golden/example.yaml --target fake`
5. `uv run --script scripts/check_corpus.py corpus/condition-briefing`

(`uv` needs the sandbox off — Dry-run lessons.)

## ACCEPTANCE CRITERIA

1. [ ] `0002` creates conditions/documents/chunks with FK, section check, HNSW + btree indexes, RLS on.
2. [ ] `0003` creates sessions/turns/recent_conditions to pane A's shape, RLS on.
3. [ ] `python -m rag.ingest` refuses a bad corpus, chunks by paragraph with stable ids, upserts; re-run never
   duplicates.
4. [ ] `rag.search` / `rag.list_conditions` match interface notes 2–3; chunks carry section, source_label, as_of.
5. [ ] `evals/contract.py` optional fields; `example.yaml` still passes against fake target.
6. [ ] `golden/condition-briefing.yaml`, 10–15 cases incl. alias, follow-up, out_of_scope ×2, domain_rule, pii.
7. [ ] ruff, pyright, unit tests clean in api/ and evals/; integration tests pass.

## OPEN QUESTIONS / ASSUMPTIONS

- **Needs from A (blocking for pyright/run, not for writing code):** `api/config.py` fields `voyage_api_key: str
  = ""`, `embedding_model: str = "voyage-4"`, `embedding_dim: int = 1024`; `api/pyproject.toml` deps `voyageai`,
  `pyyaml` (+ uv.lock); add `"rag"` to ruff isort `known-first-party`. Until A's commit lands, validate with
  `uv run --with voyageai --with pyyaml …` and a local, uncommitted cherry-pick of A's config commit — never
  commit those files from pane B.
- **Follow-up eval needs a harness change** (`session` on `GoldenCase`, `session_id` in the request). Alternative:
  drop the follow-up from the golden set and test it only in pane A's unit tests. Plan assumes the harness change.
- `pii` case expects `action="redact"` (pipeline answers with the name stripped), per ticket. If A refuses instead,
  the case needs `expect: refuse`.
- `rag.models.RetrievedChunk` duplicates `evals/contract.py` (api/ can't import evals/). Pane A may import from
  `rag` or define its own; names are identical either way.

## NOTES

- Why import `check_corpus.check` instead of copying it: one rule set; the README already tells people to run
  that script. The cost is a path-based import that only works from a repo checkout, which is where ingest runs.
- Why `delete … ord >= n`: upsert alone leaves stale tail chunks when a doc is edited to fewer paragraphs, which
  would surface unlabeled-by-current-text evidence.
- `k: 15` in the golden set: `retrieval_hit` slices `retrieved[:k]` over the concatenated three-section list.

## AMENDMENTS
