# Feature: README, deploy config, stakeholder one-pager (pane D, T4)

Validate codebase patterns before implementing. Docs-only ticket: no Python, no new dependencies.

## Feature Description

Make the condition-briefing build understandable, runnable and judgeable by a reviewer and by the stakeholder:
the README describes the actual scenario, the deploy config is confirmed for the new keys, the one-pager speaks to
strategists, and the data walkthrough tells the stakeholder about the retrieval change.

## User Story

As a reviewer (or the health-system stakeholder)
I want one README, one deploy config and one non-technical page that describe what was built and how to run it
So that I can judge the prototype without reading the code

## Problem Statement

`README.md` is still the generic kit README (generic RAG framing, `<corpus-dir>`, `<scenario>`, planned markers,
Handoff placeholders). `docs/visual/one-page.html` holds the Acme Health example. `docs/walkthrough-data.md` lacks
the retrieval talking point that `docs/architecture.md:46` says to tell the stakeholder. `docs/runbook-deploy.md`
doesn't mention `ANTHROPIC_API_KEY` / `VOYAGE_API_KEY`.

## Solution Statement

Edit four docs files in place, keeping each one's existing structure and tone. `render.yaml` already declares both
keys with `sync: false` (lines 18–23), so it needs no change unless validation finds otherwise.

## Out of Scope / Non-Goals

- Not changing: `CLAUDE.md` rubric map (pane A owns it) → listed under Needs from A.
- Not changing: `docs/tickets/`, `docs/architecture.md`, `docs/condition-briefing.prd.md` (inputs, not outputs).
- Not inventing numbers: the one-pager uses PRD targets, labeled "target", until evals/timings are measured.
- Not documenting final names that panes A/B/C haven't merged yet beyond what the ticket fixes (see Open Questions).

## Feature Metadata

**Feature Type**: Enhancement (docs + config) · **Complexity**: Low · **Systems**: README, docs/, render.yaml ·
**Dependencies**: none

## Related Work

**Implements**: `docs/tickets/condition-briefing.md#T4` · **Epic**: `docs/condition-briefing.prd.md` +
`docs/architecture.md`. Sibling tickets T1–T3 (panes A–C) define the names the README documents.

---

## CONTEXT REFERENCES

- `docs/tickets/condition-briefing.md` lines 13–32 (interface notes: routes, request, contract fields), 109–128 (T4)
- `docs/architecture.md` lines 15–23 (approach table, why the retriever is a function), 43–46 (retrieval decision)
- `docs/condition-briefing.prd.md` §1, §4, §7, §8 (problem, hypothesis, targets, non-goals)
- `docs/walkthrough-data.md` (format: numbered timed steps + Likely questions)
- `README.md` (current structure: Architecture · Run · Eval · Deploy · Handoff)
- `docs/visual/one-page.html` lines 99–137 (edit only the `page` object; JARGON list)
- `render.yaml` lines 18–23 · `docs/runbook-deploy.md` (env var section)
- `corpus/condition-briefing/README.md` (data card, link target)

---

## STEP-BY-STEP TASKS

### UPDATE README.md

- **IMPLEMENT**:
  - Intro: condition briefing for health-system strategists (three sections, every claim cited with source label +
    as-of date, clinical/out-of-scope refused). Synthetic-data statement with link to
    `corpus/condition-briefing/README.md`. Replace the Status note with the scenario's build state.
  - Architecture: mermaid shows planner → retriever (function) → answerer → critic, with the two decision points
    (planner route/refuse; critic pass / retry once / refuse) and three section-filtered searches. Short "Why the
    retriever is a function" paragraph from `docs/architecture.md:21-23`. Update the component table (guardrails
    incl. section integrity; memory = session turns + recent conditions).
  - Repository layout: reflect agents/ schemas/ guardrails/ memory/ rag/ and corpus/; mark per-pane status honestly.
  - Run: step 4 becomes `uv run python -m rag.ingest ../corpus/condition-briefing` (chunk id
    `<condition-slug>-<section>-<ord>`); step order migrate → ingest → api → ui; add `ANTHROPIC_API_KEY`,
    `VOYAGE_API_KEY` to step 1; verify step adds a sample `POST /ask` curl with the note 7 request body.
  - Eval: `golden/condition-briefing.yaml`, its case mix (answerable, alias CHF, follow-up, out_of_scope,
    domain_rule, pii) and the PRD targets.
  - Deploy: one-time setup table lists the three dashboard secrets.
  - Handoff: fill the `<…>` placeholders: `docs/condition-briefing.prd.md`, golden path, owners (strategy-team
    domain expert, corpus owner), known limits (synthetic corpus, 10 conditions, keyword search deferred, no
    freshness monitoring) and Release 2 from PRD §8 / architecture open questions.
- **GOTCHA**: CLAUDE.md says ingest runs from `api/`, so the corpus path is `../corpus/condition-briefing`.
  Don't claim pieces are built until they merge; mark them ⏳ with the owning ticket.
- **VALIDATE**: `grep -n '<scenario>\|<corpus-dir>\|<client\|<data owner>\|<product owner>\|<limit\|<non-goal\|Release 2: <' README.md` → no hits; links resolve (check script below).
- **SATISFIES**: AC 1

### CONFIRM render.yaml

- **IMPLEMENT**: verify `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY` are on `fderun-api` with `sync: false` and no
  value. Already true at lines 18–23 → no edit expected.
- **VALIDATE**: `python3 -c "import yaml,sys;d=yaml.safe_load(open('render.yaml'));e={v['key']:v for v in d['services'][0]['envVars']};assert all(e[k].get('sync') is False and 'value' not in e[k] for k in ['DATABASE_URL','ANTHROPIC_API_KEY','VOYAGE_API_KEY']);print('ok')"` (via `uv run --with pyyaml`)
- **SATISFIES**: AC 2

### UPDATE docs/runbook-deploy.md

- **IMPLEMENT**: wherever it tells you to enter `DATABASE_URL`, also list `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY`
  (same paste rules, never committed); add a note that ingest runs locally before the first demo.
- **VALIDATE**: `grep -c 'ANTHROPIC_API_KEY\|VOYAGE_API_KEY' docs/runbook-deploy.md` ≥ 2
- **SATISFIES**: AC 2 (supporting)

### UPDATE docs/visual/one-page.html (the `page` object only)

- **IMPLEMENT**: kicker "Health-system strategy · condition briefings"; before = briefing assembled by hand over
  days, stale, inconsistent, hard to trace; after = enter a condition, get three sections in under a minute, each
  statement shows its source and date, patient/clinical questions declined. Numbers (labeled targets per PRD §7):
  "< 1 min" (was: days), "100%" statements show a source, "8 of 10" first drafts accepted (target). Trust: source
  name + date beside every statement, sections never mix, "no sources for this condition" instead of guessing.
  Footer/next includes the plain statement that the sample content is made up for the demo, and the next step
  (real sources, stale-section flag).
- **GOTCHA**: the JARGON check fires on words like "model", "pipeline", "database" → avoid them. Keep the rendering
  code and JARGON list unchanged.
- **VALIDATE**: render headless and read the banner: `npx -y playwright` is heavy; instead a node one-off that
  extracts the `page` object and runs the same JARGON regex over all its strings → `0 hits`. Also open in the
  browser manually (screenshot for the lead).
- **SATISFIES**: AC 3

### UPDATE docs/walkthrough-data.md

- **IMPLEMENT**: new short step (≈30 s) after step 4, "How each section finds its evidence": semantic search
  filtered to one condition and one section; keyword search deferred because a filtered set is a handful of
  passages, and added back if the eval hit rate falls short. Renumber step 5 → 6; adjust total time (~3.5 min).
  Add a "Why not keyword search, as we discussed?" likely question.
- **VALIDATE**: `grep -n 'keyword' docs/walkthrough-data.md` shows the step and the question
- **SATISFIES**: AC 4

---

## VALIDATION COMMANDS

1. Placeholder grep on README (above) → empty.
2. Relative link check: extract `](path)` and backticked repo paths from README.md and docs/walkthrough-data.md,
   `test -e` each → all exist (planned files like `evals/golden/condition-briefing.yaml` are allowed and listed).
3. render.yaml assertion (above) → `ok`.
4. One-pager jargon check (node) → 0 hits.
5. Secret scan: `docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.30.1 dir /repo --config /repo/.gitleaks.toml --redact` → no leaks.
6. `/piv-validate`: the code suites are unchanged by this pane, so they should stay green.

## ACCEPTANCE CRITERIA

- [ ] AC 1: README covers what/architecture (4 stages, 2 decision points, retriever-as-function)/run
      (migrate → ingest → api → ui)/eval/deploy/synthetic statement + data card link; Handoff filled
- [ ] AC 2: render.yaml has both keys on the api service, no secret values
- [ ] AC 3: one-pager for strategists, jargon banner clean, unmeasured numbers labeled target
- [ ] AC 4: walkthrough has the retrieval talking point

## OPEN QUESTIONS / ASSUMPTIONS

- Ingest CLI: ticket says `python -m rag.ingest <corpus-dir>`; I document `../corpus/condition-briefing` from `api/`.
  If pane B changes the name, fix at merge (T4 merges last).
- Golden case count and real eval numbers aren't known until T2/T1 merge → README says "10–15 cases" and PRD
  targets; one-pager numbers stay "target".
- Owners in Handoff: the stakeholder named only "strategist"/"strategy team" → use roles, no names.

## Needs from A

- `CLAUDE.md` rubric map: GitHub row → "README describes the condition-briefing scenario; Handoff filled";
  Deployment row → "render.yaml confirms ANTHROPIC_API_KEY + VOYAGE_API_KEY (sync: false)".

## NOTES

Considered editing `render.yaml` comments only for cosmetics; skipped — it's correct and churn adds merge risk.

## AMENDMENTS
