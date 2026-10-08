"""Load the labeled corpus: validate it, parse front matter, chunk each document by paragraph.

Pure and offline; rag.ingest embeds and stores the result.
"""

import importlib.util
import re
from pathlib import Path
from typing import Any

import yaml

from rag.models import Chunk, Document

# Label rules live in one place: the corpus checker the data card tells people to run.
CHECKER = Path(__file__).resolve().parents[2] / "scripts" / "check_corpus.py"


class CorpusError(Exception):
    """The corpus failed validation; nothing should be ingested."""

    def __init__(self, problems: list[str]):
        super().__init__(f"{len(problems)} corpus problem(s): " + "; ".join(problems[:5]))
        self.problems = problems


def validate(root: Path) -> None:
    """Run scripts/check_corpus.py's check() on root. Raises CorpusError on any problem."""
    if not root.is_dir():
        raise CorpusError([f"{root}: not a directory"])
    if not CHECKER.exists():
        raise CorpusError([f"{CHECKER}: corpus checker not found (run from a repo checkout)"])
    spec = importlib.util.spec_from_file_location("check_corpus", CHECKER)
    if spec is None or spec.loader is None:
        raise CorpusError([f"{CHECKER}: cannot load"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    problems: list[str] = module.check(root)
    if problems:
        raise CorpusError(problems)


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Return (front matter, body) of a markdown file. Raises ValueError without front matter."""
    if not text.startswith("---\n"):
        raise ValueError("no front matter")
    _, meta, body = text.split("---\n", 2)
    data = yaml.safe_load(meta)
    if not isinstance(data, dict):
        raise ValueError("front matter is not a mapping")
    return data, body


def chunk_paragraphs(body: str) -> list[str]:
    """Split on blank lines; join each paragraph's wrapped lines into one line."""
    paragraphs = (" ".join(p.split()) for p in re.split(r"\n\s*\n", body))
    return [p for p in paragraphs if p]


def parse_document(path: Path) -> Document:
    """Parse <condition-slug>/<section>.md into a Document with stable chunk ids."""
    meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    slug, section = path.parent.name, meta["section"]
    doc = f"{slug}/{path.name}"
    chunks = [
        Chunk(
            chunk_id=f"{slug}-{section}-{ord_}",
            doc=doc,
            ord=ord_,
            condition_id=slug,
            section=section,
            text=text,
        )
        for ord_, text in enumerate(chunk_paragraphs(body))
    ]
    return Document(
        doc=doc,
        condition_id=slug,
        condition_name=meta["condition"],
        aliases=[str(a) for a in meta["aliases"]],
        section=section,
        title=meta["title"],
        source_label=meta["source_label"],
        source_type=meta["source_type"],
        as_of=meta["as_of"],
        chunks=chunks,
    )


def load_corpus(root: Path) -> list[Document]:
    """Validate, then parse every <condition>/<section>.md under root, in a stable order."""
    validate(root)
    return [parse_document(p) for p in sorted(root.glob("*/*.md"))]
