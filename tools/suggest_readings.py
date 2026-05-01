#!/usr/bin/env python3
"""Suggest complementary readings for a concept (or wiki-wide).

Walks `wiki/sources/`, aggregates each source's `cites:` frontmatter
(populated by `tools/parse_references.py`), surfaces DOIs cited by
multiple sources but not yet present in the wiki.

Usage:

    # Snowball candidates for a specific concept
    python tools/suggest_readings.py MotorImagery

    # Wiki-wide candidates (any DOI cited 2+ times across sources)
    python tools/suggest_readings.py --all

    # Only candidates cited >= N times (default 2)
    python tools/suggest_readings.py MotorImagery --min 3

    # Fetch Crossref metadata for the top results (slow, requires internet)
    python tools/suggest_readings.py MotorImagery --enrich

The --external flag (OpenAlex / Semantic Scholar fetch) is described in
CLAUDE.md but not implemented yet — left as a TODO when we want to go
beyond the existing corpus.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import yaml

REPO_ROOT = Path(__file__).parent.parent
SRC_DIR = REPO_ROOT / "wiki" / "sources"


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
    if not SRC_DIR.is_dir():
        return out
    for p in sorted(SRC_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm, body = parse_fm(text)
        out.append({"path": p, "fm": fm, "body": body, "slug": p.stem})
    return out


def crossref(doi: str) -> dict | None:
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{quote(doi, safe='/:')}",
            timeout=10,
            headers={"User-Agent": "graphbib/0.1 (mailto:contact@example.com)"},
        )
        r.raise_for_status()
        m = r.json()["message"]
        authors = [
            f"{a.get('given', '').strip()} {a.get('family', '').strip()}".strip()
            for a in m.get("author", [])
        ]
        year = None
        if m.get("issued", {}).get("date-parts"):
            year = m["issued"]["date-parts"][0][0]
        return {
            "title": (m.get("title") or [None])[0],
            "authors": [a for a in authors if a],
            "journal": (m.get("container-title") or [None])[0],
            "year": year,
        }
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("concept", nargs="?", help="Concept name (use --all for wiki-wide)")
    ap.add_argument("--all", action="store_true", help="Wiki-wide pass (no concept filter)")
    ap.add_argument("--min", type=int, default=2, help="Minimum citation count (default 2)")
    ap.add_argument("--enrich", action="store_true", help="Fetch Crossref metadata for top results")
    ap.add_argument("--top", type=int, default=50, help="Max candidates to print (default 50)")
    args = ap.parse_args()

    if not args.all and not args.concept:
        ap.error("Provide a concept name, or use --all")

    sources = load_sources()
    if not sources:
        sys.exit(f"No sources under {SRC_DIR}")

    # DOIs already in wiki (any source page that has its own doi: field)
    in_wiki = {(s["fm"].get("doi") or "").lower() for s in sources}
    in_wiki.discard("")

    # Filter by concept (look for [[ConceptName]] in the body)
    if args.all:
        relevant = sources
        scope = "wiki-wide"
    else:
        token = f"[[{args.concept}]]"
        relevant = [s for s in sources if token in s["body"]]
        scope = args.concept
        if not relevant:
            sys.exit(f"No source page references [[{args.concept}]]")

    counter: Counter[str] = Counter()
    by_doi: dict[str, list[str]] = {}
    for s in relevant:
        for raw in s["fm"].get("cites", []) or []:
            d = str(raw).lower()
            if d in in_wiki:
                continue
            counter[d] += 1
            by_doi.setdefault(d, []).append(s["slug"])

    candidates = sorted(
        [(d, n) for d, n in counter.items() if n >= args.min],
        key=lambda t: (-t[1], t[0]),
    )

    print(f"=== {len(candidates)} candidates ({scope}, min={args.min}) ===")
    for d, n in candidates[: args.top]:
        meta = crossref(d) if args.enrich else None
        slugs = by_doi[d]
        print(f"\n  [{n}x]  {d}")
        if meta:
            authors = ", ".join((meta.get("authors") or [])[:3])
            if len(meta.get("authors") or []) > 3:
                authors += " et al."
            year = meta.get("year") or "?"
            title = meta.get("title") or "?"
            journal = meta.get("journal") or ""
            print(f"          {authors} ({year}). {title}.")
            if journal:
                print(f"          {journal}")
        cited_by = ", ".join(slugs[:5]) + ("…" if len(slugs) > 5 else "")
        print(f"          cited by: {cited_by}")


if __name__ == "__main__":
    main()
