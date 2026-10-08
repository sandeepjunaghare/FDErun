# Implementation Report — Briefing UI with sources, dates, and visible memory (pane C)

**Plan**: `.claude/plans/C-briefing-ui.md`   **Branch**: `pane-c`   **Status**: COMPLETE

## Summary
The Streamlit skeleton is now the briefing screen. It streams `POST /chat` and shows the pipeline stage from
`status` events. It renders the three sections, and every cited source shows its source label, as-of date, and
doc. Each section shows its newest as-of date, and a "Synthetic sample data" badge is always visible. Refusals
and redactions render as `st.info` / `st.warning`. The sidebar shows recent conditions from `GET /recent` (click
to re-run), this session's turns, and the existing API/DB status. Until pane A's `/chat` exists, a built-in stub
streams the same events, auto-detected from `/openapi.json` or forced with `UI_STUB=1`.

## Tasks completed
- deps + pytest config → `ui/pyproject.toml`, `ui/uv.lock` (UPDATE: + pydantic, dev pytest)
- contract mirror → `ui/models.py` (CREATE)
- SSE + HTTP client → `ui/client.py` (CREATE; read timeout 60 s, connect 5 s)
- stub /chat → `ui/stub.py` (CREATE)
- view logic → `ui/briefing.py` (CREATE)
- screen → `ui/app.py` (UPDATE)
- tests → `ui/tests/test_client.py`, `test_briefing.py`, `test_stub.py` (CREATE)

## Tests added
24 unit tests, offline (`httpx.MockTransport`): SSE parsing (comments, multi-line data, unterminated event,
bad JSON), request body without/with `session_id`, HTTP error → class name only, `/chat` probe, `/recent`
shapes + 404; section split, cited-only sources, newest as-of, label/date fallbacks, `[chunk_id]` → `[n]`,
notices per action; stub event order, citations ⊆ retrieved, refusal, redaction, follow-up. 24 passed.

## Validation results
- ruff check: pass · ruff format --check: pass · pyright: 0 errors · pytest: 24 passed
- Headless app run (`streamlit.testing.v1.AppTest`, `UI_STUB=1`, API unreachable): briefing → 3 headings,
  as-of 2026-05-20 / 2026-09-12 / 2025-12-03 per section, source line with label + date; follow-up and a
  weather refusal (info, not error); sidebar lists the 3 session turns; no exceptions.
- `docker compose build ui`: pass (image builds with the new deps).

## Deviations from the plan
- `notice_for` (plan: `message_for`): renamed for clarity; same behavior.
- `annotate` takes a `SectionView` rather than `(body, sources)`: simpler call site.
- Level 4 manual check done headlessly with Streamlit's AppTest instead of a browser; a browser look is still
  worth 1 minute before the demo.
- `docker-compose.yml` not touched (no change needed), as planned.

## Issues encountered
- `uv add` / `uv run` need the sandbox off (known, dry-run lessons).

## Needs from A / lead
- A: emit inline `[chunk_id]` markers in the answer (the UI turns them into `[n]`); confirm `GET /recent` returns
  a list (or `{"conditions": [...]}`) of `{condition_id, name?, viewed_at?}`.
- Lead/CI owner: add `- name: Unit tests` / `run: uv run pytest` to the `ui` job in `.github/workflows/ci.yml`.
- Pane A owns `CLAUDE.md`: rubric map "Front end" row can move to "chat view built (stub /chat), verified after
  merge"; map line for `ui/app.py` + new modules.
