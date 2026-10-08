# PRD — Condition Briefing for Health-System Strategists

Source: `docs/discovery-notes.md` (discovery call, 2026-10-08). Anything not stated by the stakeholder is marked
**Assumption — validate via …**. Architecture (the how): `docs/architecture.md`.

> Healthcare: A health system strategy team wants a tool that generates a structured briefing for
> a given medical condition, covering the current standard of care, emerging treatments in
> development, and key companies/institutions involved.

## 1. Problem Statement

A health-system strategist who needs to understand the landscape around a medical condition has no fast,
consistent way to get it. Today a briefing is assembled by hand from scattered sources. It takes days, is partly
stale on arrival, differs in shape from one condition to the next, and its claims are hard to trace to a source.
The cost: strategic discussions (service lines, partnerships, investments) wait on research, or proceed without it.

- User and the three-section need: stated in the brief and the call.
- How briefings are produced today and what that costs: **Assumption — validate by asking one strategist how
  their last condition briefing was produced and how long it took.**

## 2. Evidence

- The brief: a health-system strategy team asked for this tool.
- Discovery call: one user, a strategist, who enters a condition and expects a clearly formatted briefing in three
  sections.
- Discovery call: the stakeholder named **freshness and source credibility** as the concern for standard-of-care
  and emerging-treatment content.
- Volume, frequency, and turnaround of briefings today: **Assumption — validate via the same strategist interview
  (briefings per quarter, days per briefing).**

## 3. Thesis (why build it)

- **Why this:** a strategist's question ("what's the landscape for condition X?") has a stable shape (standard of
  care, emerging treatments, key players), so the answer can be produced on demand in a fixed format.
- **Why now:** models can now produce a cited synthesis from a controlled set of sources in seconds, so a first
  draft no longer has to wait for analyst time. **Assumption.**
- **Why they'd switch:** minutes instead of days, every claim traceable to a source, and the same three-section
  shape for every condition so briefings can be compared side by side. **Assumption — validate in the demo
  (hypothesis below).**

## 4. Hypothesis

We believe an **on-demand, cited, three-section condition briefing** will cause **health-system strategists** to
**start from it instead of commissioning desk research**, resulting in **faster briefings they trust**.

- We'll know we're **RIGHT** if the stakeholder accepts the briefing as a usable first draft for **≥ 8 of 10**
  golden-set conditions in the demo, with every claim citing a source document.
- We'll know we're **WRONG** if **> 1 of 10** briefings contains an unsupported claim or content in the wrong
  section (e.g. an emerging treatment shown as standard of care), **or** the stakeholder says they'd still redo
  the research.

Targets are **Assumptions** set for the prototype demo.

## 5. Target User & JTBD

- **Primary user:** a strategist on a health-system strategy team (stated).
- **JTBD:** When I'm weighing a strategic move that involves a condition (a service line, a partnership, an
  investment), I want a cited briefing on its standard of care, emerging treatments, and key players, so I can join
  the discussion knowing the landscape without waiting on research. **Assumption (the trigger).**
- **Not for:** clinicians making care decisions (this is not clinical decision support), or patients.
  **Assumption.**

## 6. MVP

The thinnest line that proves the hypothesis end to end:

1. The strategist picks a condition from the sample set.
2. They get one briefing with three sections: current standard of care, emerging treatments, key
   companies/institutions. Every claim is cited.
3. A condition outside the sample set gets "no sources for this condition", never an invented answer.

- Data: an in-house sample (golden) dataset of existing conditions, per the call. Sample data is accepted for the
  prototype (**Assumption**, see open questions).
- Delivery rule from the call: get a working end-to-end slice first. Running out of time without one is a fail.
- **Door check:** sample corpus and briefing format are two-way doors (just build). How sources are labeled so
  each lands in the right section is closer to a one-way door. The stakeholder flagged it, so spike it in
  `plan-architecture`.

## 7. Success Metrics

| Metric | Target | How measured |
|---|---|---|
| First-draft acceptance | ≥ 8 of 10 golden-set conditions | Stakeholder review in the demo |
| Citation coverage | 100% of claims cite a source | Automated eval on the golden set |
| Wrong-section rate | ≤ 1 in 10 briefings | Eval on the golden set plus stakeholder review |
| Time to briefing | < 1 minute (vs. days today) | Timed in the demo |

All targets are **Assumptions** for the prototype.

## 8. Non-goals

- Clinical decision support or any patient-care advice.
- Live or external data feeds (PubMed, trial registries, news). The prototype uses the sample corpus only.
- Patient data of any kind.
- Conditions outside the sample set.
- Export or report formatting (PDF, slides).
- Freshness monitoring of sources (Release 2).

## 9. Open Questions

- [ ] How do strategists produce condition briefings today, how often, and how long does each take? (Validates
      the problem, thesis, and the "days" baseline.)
- [ ] Is sample/synthetic data acceptable to the stakeholder given their freshness and credibility concern?
      ("That's a good plan" was read as yes.)
- [ ] Regulatory constraints: the stakeholder said "you can make that up". What do we assume and state?
- [ ] Cost of a wrong answer: does an unsupported claim in a strategy briefing need a hard refusal, or a flag?
- [ ] Release 2 scope: freshness monitoring, live sources, reasoning across conditions? Not discussed.
- [ ] → `plan-architecture`: how will source records and metadata be structured, and how is content tagged or
      chunked so each section draws on the right evidence? (Stakeholder asked to be walked through it.)
- [ ] → `plan-architecture`: separate agents vs. one model plus functions. Where does anything actually need
      autonomy? (Stakeholder challenge.)
- [ ] → `plan-architecture`: which parts of the setup kit the prototype actually uses; the stakeholder's concern is
      the amount of orchestration.
