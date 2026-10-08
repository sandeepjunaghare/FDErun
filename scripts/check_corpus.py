# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Validate the condition-briefing corpus labels before ingest.

Usage: uv run --script scripts/check_corpus.py corpus/condition-briefing
"""

import datetime as dt
import sys
from pathlib import Path

import yaml

SECTIONS = {
    "standard_of_care": "guideline_summary",
    "emerging_treatments": "pipeline_digest",
    "key_institutions": "landscape_profile",
}
REQUIRED = {
    "condition",
    "aliases",
    "section",
    "title",
    "source_label",
    "source_type",
    "as_of",
    "synthetic",
}


def front_matter(path: Path) -> dict:
    """Return the YAML front matter of a markdown file, or raise ValueError."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("no front matter")
    _, meta, body = text.split("---\n", 2)
    if not body.strip():
        raise ValueError("empty body")
    return yaml.safe_load(meta)


def check(root: Path) -> list[str]:
    """Return a list of problems; empty means the corpus is valid."""
    errors: list[str] = []
    alias_owner: dict[str, str] = {}
    condition_dirs = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not condition_dirs:
        return [f"{root}: no condition folders"]
    for folder in condition_dirs:
        names: set[str] = set()
        for section, source_type in SECTIONS.items():
            path = folder / f"{section}.md"
            where = path.relative_to(root)
            if not path.exists():
                errors.append(f"{where}: missing")
                continue
            try:
                meta = front_matter(path)
            except ValueError as exc:
                errors.append(f"{where}: {exc}")
                continue
            if missing := REQUIRED - meta.keys():
                errors.append(f"{where}: missing fields {sorted(missing)}")
                continue
            if meta["section"] != section:
                errors.append(f"{where}: section {meta['section']!r} does not match file name")
            if meta["source_type"] != source_type:
                errors.append(f"{where}: source_type should be {source_type!r}")
            if meta["synthetic"] is not True:
                errors.append(f"{where}: synthetic must be true")
            if not str(meta["source_label"]).startswith("Synthetic"):
                errors.append(f"{where}: source_label must start with 'Synthetic'")
            if not isinstance(meta["as_of"], dt.date):
                errors.append(f"{where}: as_of is not an ISO date")
            names.add(meta["condition"])
            for alias in [meta["condition"], *meta["aliases"]]:
                owner = alias_owner.setdefault(alias.lower(), folder.name)
                if owner != folder.name:
                    errors.append(f"{where}: alias {alias!r} also used by {owner}")
        if len(names) > 1:
            errors.append(f"{folder.name}: condition name differs between files: {sorted(names)}")
    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "corpus/condition-briefing")
    errors = check(root)
    for error in errors:
        print(f"FAIL {error}")
    docs = len(list(root.glob("*/*.md")))
    print(f"{'FAIL' if errors else 'OK'}: {docs} documents, {len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
