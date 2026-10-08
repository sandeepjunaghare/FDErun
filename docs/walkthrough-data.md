# Walkthrough — the synthetic data (for the stakeholder)

Answers the stakeholder's concern from discovery: "for standard of care and emerging treatments we have to be
careful about freshness and source credibility." It also covers one change from the call (keyword search, step 5).
About 3½ minutes. Data card: `corpus/condition-briefing/README.md`.

## 1. Say what it is (20 s)

"This is a synthetic sample corpus: 10 chronic-care conditions, 3 documents each, one per briefing section. It
proves the briefing flow works end to end. It isn't a source of truth, and every document says so."

## 2. Open one document (40 s)

Open `corpus/condition-briefing/heart-failure/emerging_treatments.md` and point at the front matter:

- `source_label: "Synthetic pipeline digest — FDErun corpus v1"`: every label starts with "Synthetic" and names
  the kind of source it stands in for. We never cite a real journal or guideline we didn't use.
- `as_of: 2026-09-12`: every document carries the date its content describes.
- `section: emerging_treatments`: the label that keeps emerging treatments out of the standard-of-care section.

## 3. Show what's real and what's fictional (40 s)

Show the table in the data card:

- **Standard of care is real**, at a general level (drug classes, first-line approaches). It's what a strategist
  would recognize, and it ages slowly.
- **Companies, drug codes, and trial networks are fictional** and tagged "(fictional)" in the text. Made-up facts
  about real companies' pipelines would be exactly the credibility problem you raised, so we don't make any.

## 4. Show it in a briefing (60 s)

Ask for a heart failure briefing in the UI. For any cited claim, point at the **source label and as-of date shown
next to it**, and at how the dates differ by section: emerging treatments as of 2026-09, key institutions as of
2025-12. "Freshness is visible per section, not hidden behind one date for the whole briefing."

## 5. Say how each section finds its evidence (30 s)

This is a change from what we discussed on the call, so say it plainly:

"Each section runs its own search, limited to this condition and this section's documents, and ranked by meaning
rather than exact words. On the call we talked about adding keyword search alongside. We've held it back: once the
search is limited to one condition and one section there are only a handful of passages to choose from, so keyword
matching adds little. We'll add it if the test set shows sections missing the right passage."

## 6. Say what changes with real data (20 s)

"Moving to real sources means swapping the corpus, not the system: real documents get the same labels, the same
as-of dates, and the same section check. Release 2 can flag sections whose as-of date is older than a threshold
you set."

## Likely questions

- **"Is the standard of care accurate?"** At a general level, yes; it's deliberately not detailed enough to guide
  a patient decision, and the tool refuses patient-specific questions.
- **"Why not real company data?"** It would be stale on day one and we couldn't vouch for it. The fictional names
  make it obvious which parts are placeholders.
- **"How do you stop sections mixing?"** Every document has one section label; each section searches only its own
  documents, and a check rejects any claim that cites a document from another section.
- **"Didn't we talk about keyword search too?"** We deferred it, not dropped it. Filtering to one condition and one
  section leaves so few passages that meaning-based ranking finds the right one; the test set measures that on every
  run, and keyword search goes in if a section misses.
