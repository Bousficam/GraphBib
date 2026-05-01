#!/usr/bin/env python3
"""Parse references (DOIs) from a markdown source's References / Bibliography section.

Two modes:

    # Print DOIs found in a single file
    python tools/parse_references.py raw/papers/cervera-2020.md

    # Walk a directory and update each .md's frontmatter with cites: [DOIs]
    python tools/parse_references.py --all wiki/sources/

The script looks for a heading whose first word matches one of:
    references | bibliography | cited works | works cited | literature cited
    | réferences | références
and extracts every DOI-shaped string after that heading. It is intentionally
conservative: it only writes DOIs that match the canonical regex, which
avoids hallucinated entries.

Importable: `extract_dois_from_md(path: Path) -> list[str]` returns the DOIs.
"""
import re
import sys
from pathlib import Path

import yaml

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
REF_HEADERS = (
    "references",
    "bibliography",
    "cited works",
    "works cited",
    "literature cited",
    "réferences",
    "références",
)


def parse_fm(text: str):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]
            except Exception:
                pass
    return {}, text


def extract_references_block(body: str) -> str:
    """Return text after the first References/Bibliography heading."""
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith("#"):
            continue
        heading = s.lstrip("#").strip().lower().rstrip(":.")
        if any(heading == h or heading.startswith(h + " ") for h in REF_HEADERS):
            return "\n".join(lines[i + 1 :])
    return ""


def extract_dois(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in DOI_RE.finditer(text):
        d = m.group(0).rstrip(".,;)").lower()
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def extract_dois_from_md(md_path: Path) -> list[str]:
    text = md_path.read_text(encoding="utf-8")
    _, body = parse_fm(text)
    refs = extract_references_block(body)
    return extract_dois(refs)


def update_frontmatter(md_path: Path) -> list[str]:
    text = md_path.read_text(encoding="utf-8")
    fm, body = parse_fm(text)
    refs_text = extract_references_block(body)
    if not refs_text:
        return []
    dois = extract_dois(refs_text)
    if not dois:
        return []
    fm["cites"] = dois
    new_fm = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
    md_path.write_text(f"---\n{new_fm}\n---\n\n{body.lstrip()}", encoding="utf-8")
    return dois


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: parse_references.py <source-md> | --all <dir>")

    if sys.argv[1] == "--all":
        if len(sys.argv) < 3:
            sys.exit("Usage: parse_references.py --all <dir>")
        d = Path(sys.argv[2]).expanduser().resolve()
        mds = sorted(d.rglob("*.md"))
        total_refs = 0
        with_refs = 0
        for md in mds:
            dois = update_frontmatter(md)
            if dois:
                with_refs += 1
                total_refs += len(dois)
                print(f"  ✓ {md.relative_to(d)}: {len(dois)} refs")
        print(f"=== {with_refs}/{len(mds)} files updated, {total_refs} refs total ===")
    else:
        md = Path(sys.argv[1]).expanduser().resolve()
        for d in extract_dois_from_md(md):
            print(d)


if __name__ == "__main__":
    main()
