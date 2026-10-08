# Feature: Briefing UI with sources, dates, and visible memory (pane C)

The following plan should be complete, but validate documentation and codebase patterns and task sanity before
you start implementing. Stay inside `ui/`; everything else is read-only for pane C.

## Feature Description

Turn the Streamlit skeleton (`ui/app.py`, API/DB status only) into the strategist's briefing screen: enter a
condition, watch the four pipeline stages progress over SSE from `POST /chat`, read a three-section briefing in
which every cited source shows its **source label and as-of date**, ask follow-ups in the same session, and see
memory (recent conditions, session turns) in the sidebar. Works against a built-in stub stream until pane A's
`/chat` merges.

## User Story

As a health-system strategist
I want to request a condition briefing and see where each claim comes from and how fresh it is
So that I can trust the briefing enough to use it, and pick up where I left off

## Problem Statement

The UI can't chat yet (`st.chat_input(..., disabled=True)`), uses a 10 s timeout (an answerable question takes
6.5–8 s plus stream), and has no notion of sections, sources, dates, sessions, or memory, all of which the
stakeholder walkthrough (`docs/walkthrough-data.md` step 4) puts on screen.

## Solution Statement

Split the UI into small, testable modules: pydantic models mirroring the contract (`models.py`), an HTTP + SSE
client (`client.py`), a stub `/chat` stream (`stub.py`), pure view-building logic (`briefing.py`: split the
answer into the three sections, attach cited chunks with label/date, newest as-of per section), and a thin
Streamlit `app.py` that only wires state and widgets. Unit tests cover everything except `app.py`.

## Out of Scope / Non-Goals

- Not included: any API change (`/chat`, `/recent` belong to pane A), CI change to run ui tests (listed under
  Needs), auth/user login (user_id is a text field defaulting to `strategist`), freshness-threshold warnings
  (Release 2).
- Not changing: `ui/Dockerfile`, `ui/.streamlit/config.toml`, the API/DB status panel's checks, and
  `docker-compose.yml` (its ui service already sets `API_URL`; no change needed, so we avoid editing a
  non-pane-C file).

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `ui/`
**Dependencies**: streamlit, httpx (present); add `pydantic` (runtime), `pytest` (dev) to `ui/` via `uv add`

## Related Work

**Implements**: `docs/tickets/condition-briefing.md#T3` · **Epic**: `docs/condition-briefing.prd.md`,
`docs/architecture.md`
**Back-references**: none (first plan in `.claude/plans/`).
**Forward-references**: (none yet)

---

## CONTEXT REFERENCES

### Relevant Codebase Files (read before implementing)

- `ui/app.py` (all, 37 lines) - Why: skeleton; keep `get()` and the sidebar status checks, `API_URL` from env.
- `ui/pyproject.toml` - Why: ruff (line 100, rules E F W I B UP SIM), pyright standard, `package = false`.
- `evals/contract.py` (lines 15-32) - Why: `RetrievedChunk`, `AskResponse`, `Action` — mirror names exactly;
  add note-4 optional fields `section`, `source_label`, `as_of: date | None`.
- `evals/README.md` ("The /ask and /chat contract") - Why: SSE events `status {"agent"}`, `token {"text"}`,
  `done {AskResponse}`; `done` is authoritative.
- `docs/tickets/condition-briefing.md` interface notes 4, 5, 7 - Why: fields, SSE, request body
  `{"question", "user_id", "session_id"?}`; T1 adds `GET /recent?user_id=`.
- `docs/walkthrough-data.md` step 4 - Why: what the stakeholder must see (label + date next to each cited claim;
  per-section dates differ).
- `evals/tests/test_metrics.py`, `evals/pyproject.toml` lines 44-48 - Why: pytest layout to mirror
  (`pythonpath = ["."]`, `testpaths = ["tests"]`, plain functions, small factory helpers).
- `corpus/condition-briefing/README.md` - Why: the real section values and an example `source_label`/`as_of`
  for realistic stub data.

### New Files to Create

- `ui/models.py` - `Section`, `Action`, `RetrievedChunk`, `AskResponse`, `ChatRequest`, `RecentCondition`.
- `ui/client.py` - `parse_sse(lines)`, `stream_chat(...)`, `get_recent(...)`, `UiApiError`.
- `ui/stub.py` - `stub_chat_events(question)` yielding the same events a real `/chat` would.
- `ui/briefing.py` - `split_sections(answer)`, `build_briefing(resp) -> list[SectionView]`, `message_for(resp)`.
- `ui/tests/test_client.py`, `ui/tests/test_briefing.py`, `ui/tests/test_stub.py`.

### Patterns to Follow

- **Errors** (`ui/app.py:15-21`): network calls never raise into Streamlit; catch `httpx.HTTPError` and surface
  the **class name only** (`type(e).__name__`), matching the project's "public responses name the error class
  only" rule.
- **Config**: UI reads `API_URL` and the new `UI_STUB` from `os.environ` in `app.py` only (ui/ is its own
  project; the api's `config.get_settings()` rule doesn't reach it). `UI_STUB=1` forces the stub.
- **Naming**: snake_case functions, PascalCase models, module docstrings one line, JSDoc-style concision.
- **Models**: pydantic `BaseModel`, `Field(default_factory=list)`, as in `evals/contract.py`.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — deps + models

Add `pydantic` and dev `pytest`; pytest config in `ui/pyproject.toml`; `models.py`.

### Phase 2: Core — client, stub, briefing view logic (pure, tested)

### Phase 3: Integration — `app.py`

### Phase 4: Tests & validation

---

## STEP-BY-STEP TASKS

### UPDATE ui/pyproject.toml (+ ui/uv.lock)

- **IMPLEMENT**: `cd ui && uv add pydantic && uv add --dev pytest`; add
  `[tool.pytest.ini_options] pythonpath = ["."]`, `testpaths = ["tests"]`.
- **GOTCHA**: the Claude Code sandbox blocks uv's cache — run uv with the sandbox off. Don't touch `api/uv.lock`.
- **VALIDATE**: `cd ui && uv sync && uv run python -c "import pydantic, pytest"`

### CREATE ui/models.py

- **IMPLEMENT**: `Section = Literal["standard_of_care","emerging_treatments","key_institutions"]`;
  `Action = Literal["answer","refuse","redact","escalate"]`; `RetrievedChunk(chunk_id, doc, text, score: float |
  None, section: str | None, source_label: str | None, as_of: date | None)`; `AskResponse(answer, citations,
  action, retrieved)`; `ChatRequest(question, user_id, session_id: str | None)`; `RecentCondition` = permissive
  model (`condition_id: str`, `name: str | None`, `viewed_at: datetime | None`, `model_config extra="ignore"`)
  because T1 hasn't fixed `/recent`'s shape.
- **PATTERN**: `evals/contract.py:15-32`. Docstring: "Mirror of evals/contract.py — keep names in sync."
- **VALIDATE**: `cd ui && uv run pyright models.py`
- **SATISFIES**: AC 3

### CREATE ui/client.py

- **IMPLEMENT**:
  - `ChatEvent = tuple[str, dict]`; `parse_sse(lines: Iterable[str]) -> Iterator[ChatEvent]`: accumulate
    `event:` / `data:` (multi-line data joined with `\n`), emit on blank line, ignore `:` comments, default event
    `message`, JSON-decode data.
  - `stream_chat(api_url, req, *, client=None) -> Iterator[ChatEvent]`: `httpx.stream("POST", f"{api_url}/chat",
    json=req.model_dump(exclude_none=True), timeout=httpx.Timeout(60, connect=5))`, `raise_for_status()`, yield
    from `parse_sse(r.iter_lines())`. Accepts an injected `httpx.Client` for tests (`MockTransport`).
  - `chat_available(api_url) -> bool`: probe `GET /openapi.json` for `"/chat"` in paths (FastAPI exposes it) —
    lets the UI auto-pick the stub before A merges.
  - `get_recent(api_url, user_id) -> list[RecentCondition]`: `GET /recent?user_id=`; 404/HTTP error → `[]`.
    Accept either a bare list or `{"conditions": [...]}`.
  - `UiApiError(Exception)` wrapping `httpx.HTTPError` / bad JSON with the class name.
- **GOTCHA**: timeout ≥ 30 s (read timeout 60). `exclude_none` keeps `{"question","user_id"}` when no session.
- **VALIDATE**: `cd ui && uv run pytest tests/test_client.py`
- **SATISFIES**: AC 2

### CREATE ui/stub.py

- **IMPLEMENT**: `stub_chat_events(question: str) -> Iterator[ChatEvent]`: status planner → retriever →
  answerer → critic (short `time.sleep`, parameterised `delay=0.3` so tests pass `0`), then token chunks, then
  `done` with an `AskResponse` for heart failure: three headings, citations to 4–6 fake chunks with sections,
  labels like `Synthetic — clinical guideline summary`, as-of dates differing by section (2026-09 emerging,
  2025-12 institutions). Questions containing "weather" or "should I" → `done` with `action="refuse"`; a name
  like "patient John" → `action="redact"`. Stub-mode banner in the UI.
- **VALIDATE**: `cd ui && uv run pytest tests/test_stub.py`
- **SATISFIES**: AC 6

### CREATE ui/briefing.py

- **IMPLEMENT**:
  - `HEADINGS = {"Current standard of care": "standard_of_care", "Emerging treatments": "emerging_treatments",
    "Key companies and institutions": "key_institutions"}` (T1's fixed headings).
  - `split_sections(answer) -> dict[Section, str]`: split on `^## ` lines; unknown/missing headings → text kept
    under a `None` "preamble" key so nothing is silently dropped.
  - `SourceRef(chunk_id, source_label, as_of, doc)`; `SectionView(section, title, body, sources, newest_as_of)`.
  - `build_briefing(resp) -> list[SectionView]`: cited chunks = `retrieved` filtered to `citations`; assign to a
    section by `chunk.section`, falling back to "the section whose body mentions the chunk_id"; `newest_as_of` =
    max non-null `as_of` in the section. Missing label/date render as "label unavailable" / "date unknown".
  - `annotate(body, sources) -> str`: replace inline `[chunk_id]` markers with `[n]` footnote numbers that match
    the source list (only if markers exist; harmless otherwise).
  - `message_for(resp) -> tuple[Literal["info","warning"], str] | None`: refuse → info with `resp.answer`
    (or a default "This assistant only gives condition briefings…"); redact → warning "Patient identifiers were
    removed before processing"; escalate → info.
- **VALIDATE**: `cd ui && uv run pytest tests/test_briefing.py`
- **SATISFIES**: AC 3, 4

### UPDATE ui/app.py

- **IMPLEMENT**:
  - `st.set_page_config(page_title="Condition briefing", layout="wide")`, title + `st.badge`/caption
    "🧪 Synthetic sample data" always visible.
  - Session state: `user_id` (sidebar text input, default `strategist`), `session_id` (`uuid4().hex`, new on
    "New briefing"), `turns: list[dict]` (role, content, AskResponse | None).
  - Mode: `UI_STUB=1` or `not chat_available(API_URL)` → stub (banner "Stub /chat — pane A's API not merged").
  - Input: `st.chat_input("Condition (e.g. heart failure) or a follow-up")`; also a sidebar "recent" button sets
    a pending question in state and `st.rerun()`.
  - On submit: append user turn; `with st.status("Planner…", expanded=False) as s:` update label per `status`
    event (planner → retriever → answerer → critic); `st.write_stream` the `token` texts into a placeholder; on
    `done` replace the placeholder with the rendered briefing (authoritative). `UiApiError` → `st.error` with
    the class name, turn kept.
  - Render briefing: per `SectionView`: `### title` + "as of <newest>" caption, annotated body, then a compact
    sources list `[n] source_label · as of YYYY-MM-DD · doc`.
  - Refuse/redact via `message_for` → `st.info` / `st.warning`, never `st.error`.
  - Sidebar: existing API/DB status (keep `get()`, raise its timeout only where it calls /chat — status checks
    stay at 10 s); "Recent conditions" from `get_recent` (buttons re-run "Briefing on <name>"); "This session"
    list of past turns (question + action), so memory is visible.
  - Cache `chat_available` and status checks with `st.cache_data(ttl=30)` so every rerun doesn't hit the API.
- **GOTCHA**: Streamlit reruns the script on every interaction: rendering of history must come from
  `st.session_state.turns`, not from the stream. Pyright: `st.session_state` values are `Any` — cast at read.
- **VALIDATE**: `cd ui && uv run ruff check . && uv run ruff format --check . && uv run pyright`;
  `UI_STUB=1 uv run streamlit run app.py` + manual check (Level 4).
- **SATISFIES**: AC 1–6

### CREATE ui/tests/*

- **IMPLEMENT**: see Testing Strategy. Add `ui/.dockerignore` entry `tests/` only if it doesn't bloat — optional.
- **VALIDATE**: `cd ui && uv run pytest`

---

## TESTING STRATEGY

### Unit Tests (pytest, offline)

- `test_client.py`: `parse_sse` — single event, multi-line data, comments, missing trailing blank line flushes
  nothing (documented), malformed JSON → `UiApiError`. `stream_chat` with `httpx.MockTransport` returning a
  canned SSE body: yields status×4, tokens, done; request body omits `session_id` when None; 503 →
  `UiApiError("HTTPStatusError")`. `get_recent`: list shape, dict shape, 404 → `[]`.
- `test_briefing.py`: `split_sections` on the three headings; missing heading; `build_briefing` attaches only
  cited chunks, by `section`, newest as-of per section, null label/date fallbacks; `annotate` numbering;
  `message_for` per action.
- `test_stub.py`: event order planner→retriever→answerer→critic→token…→done; `done` validates as `AskResponse`;
  every citation ⊆ retrieved ids; refusal and redact triggers.

### Integration Tests

None in ui/ (no network in unit tests). End-to-end is the manual check after A merges.

### Edge Cases

`done` with no citations; `done` without preceding tokens (refusal); stream drops before `done` (show error,
keep partial text marked unchecked? — **no**: discard partial text, show error, because tokens are checked but
`done` is authoritative); unknown event names ignored; `/recent` missing (pre-merge) → empty sidebar section.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
`cd ui && uv run ruff check . && uv run ruff format --check . && uv run pyright`

### Level 2: Unit Tests
`cd ui && uv run pytest`

### Level 3: Integration
`docker compose build ui` (image still builds with the new deps).

### Level 4: Manual Validation
`cd ui && UI_STUB=1 uv run streamlit run app.py` → <http://localhost:8711>: ask "heart failure" (stages advance,
three sections, label + date per source, different as-of per section, synthetic badge); follow-up shows in
"This session"; "What's the weather?" → info message not error; API status panel still renders.

---

## ACCEPTANCE CRITERIA

1. Condition input + follow-up in one session; `session_id` in Streamlit state, sent on every turn.
2. Streams `/chat`; stage shown from `status` events; HTTP read timeout ≥ 30 s.
3. Three sections; each cited source shows source label + as-of date; each section shows its newest as-of date;
   "Synthetic sample data" badge visible.
4. Refusals and redactions render as a clear message, not an error.
5. Sidebar: recent conditions from `GET /recent` (click re-runs); session turns visible.
6. Works against a stub `/chat` until A merges; existing API/DB status panel kept.
7. ruff, ruff format, pyright, pytest all clean in `ui/`.

## COMPLETION CHECKLIST

- [ ] All tasks done in order, each validation passed
- [ ] Level 1–3 green; Level 4 checked in the browser
- [ ] Only `ui/` and this plan changed

---

## OPEN QUESTIONS / ASSUMPTIONS

- **Inline citation format** isn't fixed by T1. Assumption: answers may contain `[chunk_id]` markers; the UI
  doesn't depend on them (sources are grouped by `chunk.section`). Ask A to emit `[chunk_id]` inline so the
  `[n]` footnotes line up with claims.
- **`GET /recent` response shape** isn't fixed. Assumption: list of `{condition_id, name, viewed_at}` (bare
  list or under `conditions`). Ask A to confirm.
- **Stub detection** via `/openapi.json` assumes A leaves FastAPI's docs on. `UI_STUB` overrides either way.
- **docker-compose.yml**: ticket lists it, but no change is needed, so pane C leaves it alone.

## Needs from others

- **A**: confirm `/recent` shape and inline `[chunk_id]` markers (above).
- **Lead / CI owner**: add `- name: Unit tests\n  run: uv run pytest` to the `ui` job in
  `.github/workflows/ci.yml` (not a pane-C file).

## NOTES

- Rejected: `httpx-sse` dependency — 20 lines of parser are easier to test than a new lib that hasn't had a dry
  run (working principle: no library without a dry run).
- Rejected: importing `evals/contract.py` — the ui Docker build context is `./ui`, so it must be mirrored.
- Size estimate: ~250 app code + ~200 tests.

## AMENDMENTS
