"""Citation check and the domain rule (section integrity), on the typed draft."""

from schemas import SECTIONS, BriefingDraft, FollowUpDraft, RetrievedChunk


def check_draft(draft: BriefingDraft | FollowUpDraft, retrieved: list[RetrievedChunk]) -> list[str]:
    """Return the problems found; an empty list means the draft passes.

    Every claim cites at least one chunk, every cited chunk was retrieved, and (briefings only)
    a claim under a section cites only chunks labeled with that section.
    """
    by_id = {c.chunk_id: c for c in retrieved}
    problems: list[str] = []
    if isinstance(draft, FollowUpDraft):
        if not draft.claims:
            problems.append("the answer has no claims")
        for claim in draft.claims:
            problems += _claim_problems(claim.text, claim.chunk_ids, by_id, section=None)
        return problems
    for section in SECTIONS:
        claims = getattr(draft, section)
        if not claims:
            problems.append(f"section {section} has no claims")
        for claim in claims:
            problems += _claim_problems(claim.text, claim.chunk_ids, by_id, section)
    return problems


def _claim_problems(
    text: str, chunk_ids: list[str], by_id: dict[str, RetrievedChunk], section: str | None
) -> list[str]:
    if not chunk_ids:
        return [f"claim cites nothing: {text!r}"]
    problems = []
    for cid in chunk_ids:
        chunk = by_id.get(cid)
        if chunk is None:
            problems.append(f"claim cites {cid}, which was not retrieved: {text!r}")
        elif section is not None and chunk.section != section:
            problems.append(
                f"claim under {section} cites {cid} from section {chunk.section}: {text!r}"
            )
    return problems
