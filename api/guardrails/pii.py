"""Redact patient identifiers from the question before it is stored or sent to a model.

Regex only, so it catches identifiers with a cue (a title, "patient", "MRN", "DOB"); a bare name
with no cue word passes through. All-caps tokens are never treated as names, so aliases like
CHF or COPD survive.
"""

import re

_NAME = r"[A-Z][a-z]+(?:[ '-][A-Z][a-z]+)?"
_DATE = r"\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}"

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    (
        "MRN",
        re.compile(r"\b(?:MRN|medical record(?: number)?)\s*(?:#|:|no\.?)?\s*[A-Z0-9-]{4,}", re.I),
    ),
    ("DOB", re.compile(rf"\b(?:DOB|date of birth|born(?: on)?)\s*:?\s*{_DATE}", re.I)),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b")),
    # Cue word + capitalised name: "patient John Smith", "Mrs. Lee", "named Ana Ruiz".
    (
        "NAME",
        re.compile(rf"\b(?:(?i:patient|pt\.?|named|called)|Mr\.?|Mrs\.?|Ms\.?|Miss)\s+{_NAME}\b"),
    ),
]


def redact(text: str) -> tuple[str, list[str]]:
    """Return (redacted text, kinds of identifier found, in pattern order)."""
    found: list[str] = []
    for kind, pattern in PATTERNS:
        if kind == "NAME":
            text, n = pattern.subn(_keep_cue, text)
        else:
            text, n = pattern.subn(f"[REDACTED-{kind}]", text)
        if n:
            found.append(kind)
    return text, found


def _keep_cue(m: re.Match[str]) -> str:
    """Keep the cue word ("patient") so the question still reads, drop the name."""
    cue = m.group(0).split()[0]
    return f"{cue} [REDACTED-NAME]"
