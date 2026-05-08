#!/usr/bin/env python3
"""Maintain `## Cited By` sections across wiki/sources/.

For each source page S with a `doi:` in its frontmatter, find every other
source page whose `cites:` frontmatter contains S's DOI, and rewrite S's
`## Cited By` section with wikilinks to those papers.

Usage:
    python tools/update_cited_by.py             # update wiki-wide
    python tools/update_cited_by.py --dry-run    # report what would change
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SRC_DIR = REPO_ROOT / "wiki" / "sources"

CITED_BY_HEADER = "## Cited By"
NEXT_SECTION_RE = re.compile(r"^## ", re.MULTILINE)


def parse_fm(text: str):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]
            except Exception:
                pass
    return {}, text


def load_sources():
    out = []
    for p in sorted(SRC_DIR.rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm, body = parse_fm(text)
        out.append({"path": p, "fm": fm, "body": body, "slug": p.stem, "raw": text})
    return out


def replace_section(body: str, header: str, new_content: str) -> str:
    """Replace the section starting with `header` (until next `## ` or EOF)."""
    idx = body.find(header)
    if idx == -1:
        # Section not present: append at end.
        sep = "\n\n" if not body.endswith("\n") else "\n"
        return body + sep + header + "\n" + new_content + "\n"

    after = body[idx + len(header) :]
    next_match = NEXT_SECTION_RE.search(after)
    if next_match:
        end = idx + len(header) + next_match.start()
        return body[:idx] + header + "\n" + new_content + "\n\n" + body[end:]
    else:
        return body[:idx] + header + "\n" + new_content + "\n"


def render_cited_by(citers: list[str]) -> str:
    if not citers:
        return "*(No wiki source currently cites this paper.)*"
    return "\n".join(f"- [[{slug}]]" for slug in sorted(citers))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not SRC_DIR.is_dir():
        sys.exit(f"No source directory at {SRC_DIR}")

    sources = load_sources()

    # Index: DOI -> slug
    doi_to_slug: dict[str, str] = {}
    for s in sources:
        d = (s["fm"].get("doi") or "").strip().lower()
        if d:
            doi_to_slug[d] = s["slug"]

    # Reverse index: target slug -> [citing slugs]
    cited_by: dict[str, list[str]] = {slug: [] for slug in doi_to_slug.values()}
    for s in sources:
        for raw in s["fm"].get("cites", []) or []:
            d = str(raw).strip().lower()
            target = doi_to_slug.get(d)
            if target and target != s["slug"]:
                cited_by[target].append(s["slug"])

    n_updated = 0
    for s in sources:
        if s["slug"] not in cited_by:
            continue
        new_content = render_cited_by(cited_by[s["slug"]])
        new_body = replace_section(s["body"], CITED_BY_HEADER, new_content)
        if new_body == s["body"]:
            continue
        n_updated += 1
        if args.dry_run:
            print(f"  would update: {s['path'].relative_to(REPO_ROOT)} ({len(cited_by[s['slug']])} citers)")
        else:
            fm_text = yaml.safe_dump(s["fm"], allow_unicode=True, sort_keys=False).strip()
            s["path"].write_text(f"---\n{fm_text}\n---\n\n{new_body.lstrip()}", encoding="utf-8")
            print(f"  ✓ {s['path'].relative_to(REPO_ROOT)} ({len(cited_by[s['slug']])} citers)")

    print(f"=== {n_updated}/{len(sources)} source pages {'would be ' if args.dry_run else ''}updated ===")


if __name__ == "__main__":
    main()
