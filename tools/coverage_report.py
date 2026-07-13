#!/usr/bin/env python3
"""Coverage report - surface where the wiki is thin.

Walks the wiki and reports on:

  - Concept pages by depth (stub / page / chapter):
      stub    = < 500 words
      page    = 500-1500 words
      chapter = >= 1500 words
  - Concepts mentioned ≥ 3 times in sources but still stubs (priority expansions)
  - Method/intervention pages without a `## Used In This Wiki` populated section
  - Sources without intervention_family or methods (under-tagged)

Usage:
    python tools/coverage_report.py
    python tools/coverage_report.py --save  # writes wiki/coverage-report.md

Zero LLM calls; uses Read + Grep equivalents.
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR  # noqa: E402

WIKILINK_RE = re.compile(r"\[\[([A-Za-z0-9\-_/.]+)\]\]")


def parse_fm(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]
            except Exception:
                pass
    return {}, text


def word_count(body):
    return len(re.findall(r"\w+", body))


def depth_label(n):
    if n < 500:
        return "stub"
    if n < 1500:
        return "page"
    return "chapter"


def walk_dir(subdir):
    d = WIKI_DIR / subdir
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm, body = parse_fm(text)
        out.append({"slug": p.stem, "path": p, "fm": fm, "body": body, "wc": word_count(body)})
    return out


def count_mentions_in_sources(slug, sources):
    """Count how many source pages contain [[slug]]."""
    n = 0
    for s in sources:
        if f"[[{slug}]]" in s["body"]:
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true", help="Write to wiki/coverage-report.md")
    args = ap.parse_args()

    if not WIKI_DIR.is_dir():
        sys.exit(f"No wiki/ at {WIKI_DIR}")

    sources = walk_dir("sources")
    concepts = walk_dir("concepts")
    methods = walk_dir("methods")
    interventions = walk_dir("interventions")
    questions = walk_dir("questions")
    recommendations = walk_dir("recommendations")

    lines = ["# Coverage Report", ""]

    # ---- Concepts depth ----
    lines.append("## Concepts - depth distribution")
    lines.append("")
    if not concepts:
        lines.append("*(No concept pages yet.)*")
    else:
        depths = Counter(depth_label(c["wc"]) for c in concepts)
        lines.append(f"- Total: **{len(concepts)}** concepts")
        for d in ("stub", "page", "chapter"):
            n = depths.get(d, 0)
            pct = (n / len(concepts) * 100) if concepts else 0
            lines.append(f"- {d.capitalize()}: {n} ({pct:.0f}%)")
    lines.append("")

    # ---- Stubs that should be chapters ----
    lines.append("## Priority concept expansions (mentioned ≥ 3 times, still stub)")
    lines.append("")
    priorities = []
    for c in concepts:
        if c["wc"] >= 500:
            continue
        n = count_mentions_in_sources(c["slug"], sources)
        if n >= 3:
            priorities.append((n, c["slug"], c["wc"]))
    priorities.sort(reverse=True)
    if not priorities:
        lines.append("*(None - every well-mentioned concept has at least page-depth.)*")
    else:
        for n, slug, wc in priorities[:20]:
            lines.append(f"- [[{slug}]] - {n} sources, {wc} words")
    lines.append("")

    # ---- Methods/Interventions without Used-In population ----
    lines.append("## Methods without recorded usage")
    lines.append("")
    bare = [m for m in methods if "## Used In This Wiki" not in m["body"] or "[[" not in m["body"].split("## Used In This Wiki", 1)[1]]
    if not bare:
        lines.append("*(All method pages list at least one source.)*")
    else:
        for m in bare:
            lines.append(f"- [[methods/{m['slug']}]] ({m['wc']} words)")
    lines.append("")

    lines.append("## Interventions without recorded usage")
    lines.append("")
    bare = [i for i in interventions if "## Used In This Wiki" not in i["body"] or "[[" not in i["body"].split("## Used In This Wiki", 1)[1]]
    if not bare:
        lines.append("*(All intervention pages list at least one source, or no interventions yet.)*")
    else:
        for i in bare:
            lines.append(f"- [[interventions/{i['slug']}]] ({i['wc']} words)")
    lines.append("")

    # ---- Sources under-tagged ----
    lines.append("## Sources with no `methods:` and no `intervention_family:`")
    lines.append("")
    untagged = [
        s for s in sources
        if not (s["fm"].get("methods") or s["fm"].get("intervention_family"))
    ]
    if not untagged:
        lines.append("*(All sources are tagged.)*")
    else:
        lines.append(f"{len(untagged)} sources missing both fields:")
        for s in untagged[:30]:
            lines.append(f"- [[{s['slug']}]]")
        if len(untagged) > 30:
            lines.append(f"- … and {len(untagged) - 30} more")
    lines.append("")

    # ---- Open questions ----
    lines.append("## Open questions count")
    lines.append("")
    open_q = [q for q in questions if "open" in (q["fm"].get("status") or "open").lower()]
    lines.append(f"- {len(open_q)} open / {len(questions)} total")
    lines.append("")

    # ---- Recommendations ----
    lines.append("## Recommendations count")
    lines.append("")
    lines.append(f"- {len(recommendations)} recommendation pages")
    lines.append("")

    # ---- Summary ----
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Sources: {len(sources)}")
    lines.append(f"- Concepts: {len(concepts)} ({sum(1 for c in concepts if c['wc'] >= 1500)} chapters)")
    lines.append(f"- Methods: {len(methods)}")
    lines.append(f"- Interventions: {len(interventions)}")
    lines.append(f"- Recommendations: {len(recommendations)}")
    lines.append(f"- Open Questions: {len(open_q)}")

    output = "\n".join(lines)

    if args.save:
        target = WIKI_DIR / "coverage-report.md"
        target.write_text(output + "\n", encoding="utf-8")
        print(f"  ✓ {target.relative_to(REPO_ROOT)}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
