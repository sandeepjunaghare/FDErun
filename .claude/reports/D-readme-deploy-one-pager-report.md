# Implementation Report — README, deploy config, stakeholder one-pager (pane D, T4)

**Plan**: `.claude/plans/D-readme-deploy-one-pager.md`   **Branch**: `pane-d`   **Status**: COMPLETE

## Summary

README now describes the condition-briefing build: what it does, the synthetic-data statement with a link to the
data card, the four stages with the two decision points and why the retriever is a function, and the run order
(migrate → ingest `../corpus/condition-briefing` → api → ui). It also covers a sample `/ask`, the golden set and
PRD pass bar, deploy with all three secrets, and a filled-in Handoff. `render.yaml` was confirmed as already
correct. The one-pager is rewritten for strategists. The data walkthrough has the retrieval / keyword-search
talking point.

## Tasks completed

- README → `README.md` (UPDATE: intro, architecture, layout, Run 1/3/4/5/6, Eval, Deploy, Handoff)
- render.yaml → confirmed, no edit (`ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `DATABASE_URL`: `sync: false`, no value)
- Deploy runbook → `docs/runbook-deploy.md` (UPDATE: three secrets, one-time ingest step, paste step)
- One-pager → `docs/visual/one-page.html` (UPDATE: `page` object, `<title>`)
- Walkthrough → `docs/walkthrough-data.md` (UPDATE: new step 5, likely question, timing)

## Tests added

None (docs-only ticket).

## Validation results

- README placeholder grep (`<scenario>`, `<corpus-dir>`, `<client…>`, `<slug>` …): 0 hits — PASS
- Relative links / repo paths: all resolve except `api/agents/`, `api/rag/`, `evals/golden/condition-briefing.yaml`,
  which arrive with T1/T2 (marked ⏳ in the README) — PASS (expected)
- render.yaml assertion (3 secrets on `fderun-api`, `sync: false`, no value): `render.yaml ok` — PASS
- One-pager jargon check (same regex and list as the page, run in node over the `page` strings): 0 hits — PASS
- gitleaks v8.30.1 on the changed files: no leaks found — PASS
- One-pager visual render: NOT RUN (headless Chrome won't start in the sandbox) — open it in a browser

## Deviations from the plan

- `<title>` of the one-pager changed from "One-page visual" to "Condition Briefings": metadata, not rendered content.
- gitleaks ran on a copy of the changed files, not `dir /repo`: a full-directory scan would read the gitignored
  `.env`. CI still scans full history.
- render.yaml validated with `api/.venv` Python (uv couldn't fetch PyYAML inside the sandbox).

## Issues encountered

- The one-pager now has 4 trust lines (was 3); check in a browser that the 16:9 card doesn't overflow at 1280 px.
- Ingest command and golden-set file follow the ticket; if pane B ships different names, fix at merge (T4 merges last).

## Needs from A

- `CLAUDE.md` rubric map: GitHub → "README describes the condition-briefing scenario; Handoff filled";
  Deployment → "render.yaml confirms ANTHROPIC_API_KEY + VOYAGE_API_KEY (sync: false); runbook lists all three".
  Commands → ingest example `../corpus/condition-briefing` instead of `<corpus-dir>`.
