# Condition-briefing corpus (synthetic) — data card

Sample corpus for the condition-briefing prototype (`docs/condition-briefing.prd.md`). **Every document is
synthetic.** It exists to prove the briefing flow end to end, not to inform clinical or strategic decisions.

## What's in it

10 conditions × 3 sections = 30 documents, one file per condition and section:

```
<condition-slug>/standard_of_care.md      source_type: guideline_summary
<condition-slug>/emerging_treatments.md   source_type: pipeline_digest
<condition-slug>/key_institutions.md      source_type: landscape_profile
```

Conditions: type 2 diabetes, heart failure, COPD, asthma, chronic kidney disease, atrial fibrillation, rheumatoid
arthritis, Alzheimer's disease, major depressive disorder, non-small cell lung cancer.

## What's real and what's fictional

| Section | Content | Why |
|---|---|---|
| Standard of care | Real, well-established practice, kept at a general level (drug classes, first-line approaches, monitoring) | Strategists will recognize it; general statements age slowly |
| Emerging treatments | **Fictional** companies and drug codes, with plausible mechanisms and phases | Invented facts about real companies' pipelines would be stale or wrong, which is exactly the credibility risk the stakeholder raised |
| Key institutions | **Fictional** companies, registries, and trial networks, plus generic real-world actor types (regulators, payers, research funders, advocacy groups) | Same reason; no claim is made about a named real organization |

Every fictional name is tagged `(fictional)` in the text. Any resemblance to a real company is unintended.

## Labels on every document

Each file starts with YAML front matter. The ingest carries these onto every chunk, and the UI shows the source
label and as-of date next to each cited claim.

| Field | Meaning |
|---|---|
| `condition`, `aliases` | Canonical name and alternate names the planner resolves (e.g. "CHF" → heart failure) |
| `section` | `standard_of_care` · `emerging_treatments` · `key_institutions`; the retriever filters on it, and the section-integrity rule checks it |
| `title` | Human-readable document title |
| `source_label` | Always starts with "Synthetic" and names the kind of source modeled. Never cites a real journal, guideline body, or paper |
| `source_type` | `guideline_summary` · `pipeline_digest` · `landscape_profile` |
| `as_of` | The date the content describes (ISO). Dates vary between 2025-11 and 2026-09 so freshness is visible per section |
| `synthetic` | Always `true` |

## Writing rules

- Each paragraph stands on its own and names the condition, so any one chunk is still readable when retrieved
  alone.
- Standard-of-care paragraphs never mention companies; emerging-treatment paragraphs never restate standard of care.
  That keeps sections cleanly separable.
- Not clinical advice. The prototype refuses patient-specific questions.

## Check and load

```bash
uv run --script scripts/check_corpus.py corpus/condition-briefing    # labels, sections, dates
cd api && uv run python -m rag.ingest ../corpus/condition-briefing  # after migrate (pane B's ingest)
```
