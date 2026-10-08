# Implementation Report — Condition-briefing retrieval (pane B, T2)

**Plan**: `.claude/plans/B-condition-briefing-retrieval.md`   **Branch**: `pane-b`   **Status**: COMPLETE (pending Needs from A)

## Summary
The synthetic corpus is now in Supabase (10 conditions, 30 documents, 131 paragraph chunks, voyage-4 1024-dim)
and searchable by condition + section via `rag.search.search`; `rag.list_conditions` serves the planner. Memory
tables exist for pane A. The eval contract carries source label/section/as-of, the harness supports multi-turn
sessions, and `golden/condition-briefing.yaml` has 14 cases.

## Tasks completed
- Corpus schema → `api/db/migrations/0002_condition_briefing.sql` (CREATE) — applied to Supabase
- Memory schema → `api/db/migrations/0003_memory.sql` (CREATE) — applied to Supabase
- `api/rag/{__init__,models,corpus,embed,ingest,search,conditions}.py` (CREATE)
- `evals/contract.py`, `evals/targets.py`, `evals/run.py` (UPDATE) — optional chunk labels; `session` cases
- `evals/golden/condition-briefing.yaml` (CREATE) — 7 briefings, alias, 2-turn follow-up, 2 out_of_scope,
  domain_rule, pii
- Tests: `api/tests/test_rag_corpus.py`, `test_rag_search.py`, `test_rag_integration.py`; `evals/tests/test_run.py` (+3)

## Tests added
- api unit: 9 (chunking, front matter + stable ids, bad corpus refused, missing dir, real corpus loads 30/10,
  search SQL filters + label mapping, list_conditions, missing key → EmbeddingError, pgvector literal) — pass
- api integration: ingest twice → same counts, search returns only the filtered doc with label + date, sorted;
  unknown condition → []; 10 conditions, CHF alias — pass
- evals: session ordering + per-run session_id; HttpTarget sends session_id only when set; RetrievedChunk labels — pass

## Validation results
- api: ruff ✓, ruff format ✓, pyright 0 errors, pytest 32 passed, `-m integration` 3 passed
- evals: ruff ✓, format ✓, pyright 0 errors, pytest 26 passed, example.yaml PASS 4/4 on fake target
- migrate: 0002 + 0003 applied; ingest ×2: 10 conditions, 30 documents, 131 chunks both runs (~6 s)
- golden check: every `contains` phrase found in its doc; direct retrieval preview 10/10 answerable cases hit at k=15
- corpus check: OK, 30 documents

## Deviations from the plan
- `rag/__init__.py` does not re-export `search`: doing so shadows the `rag.search` module (breaks
  monkeypatching and pyright). Import with `from rag.search import search` — the path interface note 2 names.
- Async tests use the anyio pytest plugin (already installed via FastAPI); no new dev dependency.
- `Target.ask` gained `session_id: str | None = None`; the `Down` test stub was updated to match the protocol.

## Issues encountered
- `api/config.py` lacks the Voyage settings and `api/pyproject.toml` lacks `voyageai`/`pyyaml` (pane A owns both).
  Validated with a temporary, uncommitted config edit and `uv pip install` into the local `.venv`; neither is
  committed. Pyright and the unit tests will fail on this branch alone until A's change merges.

## Needs from A
- `api/config.py` `Settings`: `voyage_api_key: str = ""`, `embedding_model: str = "voyage-4"`, `embedding_dim: int = 1024`
- `api/pyproject.toml` + `uv.lock`: `uv add voyageai pyyaml` (dev: `types-PyYAML` optional — pyright is clean without it)
- `[tool.ruff.lint.isort] known-first-party`: add `"rag"`
- Retriever: `from rag.search import search`; planner: `from rag import list_conditions`; `rag.RetrievedChunk`
  matches `evals/contract.py` field-for-field
