"""Turn a checked draft into the markdown the user sees, so what was checked is what is shown."""

from schemas import SECTION_HEADINGS, SECTIONS, BriefingDraft, Claim, FollowUpDraft


def _bullet(claim: Claim) -> str:
    return f"- {claim.text.strip()} [{', '.join(claim.chunk_ids)}]"


def to_markdown(draft: BriefingDraft | FollowUpDraft) -> str:
    if isinstance(draft, FollowUpDraft):
        return "\n".join(_bullet(c) for c in draft.claims)
    parts = []
    for section in SECTIONS:
        parts.append(SECTION_HEADINGS[section])
        parts += [_bullet(c) for c in getattr(draft, section)]
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def citations_of(draft: BriefingDraft | FollowUpDraft) -> list[str]:
    """Cited chunk ids, in order of first use."""
    claims = (
        draft.claims
        if isinstance(draft, FollowUpDraft)
        else [c for s in SECTIONS for c in getattr(draft, s)]
    )
    return list(dict.fromkeys(cid for c in claims for cid in c.chunk_ids))


def token_chunks(markdown: str) -> list[str]:
    """Split into line pieces for `token` events; joined, they equal the input."""
    return markdown.splitlines(keepends=True)
