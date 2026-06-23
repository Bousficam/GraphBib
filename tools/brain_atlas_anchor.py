#!/usr/bin/env python3
"""Atlas anchoring — link sources to anatomical / structural anchors they discuss.

Walks `wiki/sources/`, scans each body for region / tract mentions declared
in `tools/data/domain.json` (`regions` and `tracts` sections). Outputs:

    1. Per-region report: which papers discuss each region or tract,
       with a sentence-level snippet for context.
    2. A "what's known about X" view per region — Markdown that can be
       saved into wiki/ as the basis of a region anchor page.

The anatomy vocabulary is NOT hardcoded — the shipped default
(`tools/data/domain.json`) is the neutral baseline (empty), so this tool
only does something once a domain pack declaring `regions` / `tracts` is
configured. See `tools/data/domain.stroke.example.json` for a neuroimaging
example.

Usage:
    python tools/brain_atlas_anchor.py
    python tools/brain_atlas_anchor.py --region M1
    python tools/brain_atlas_anchor.py --save                # writes wiki/syntheses/atlas-anchor.md
    python tools/brain_atlas_anchor.py --region M1 --save-region   # writes wiki/concepts/M1-atlas.md
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR, load_domain, load_sources  # noqa: E402

DOMAIN_HINT = (
    "No anatomical anchors configured. Add `regions` and/or `tracts` to "
    "tools/data/domain.json, or activate the example pack:\n"
    "    cp tools/data/domain.stroke.example.json tools/data/domain.json\n"
    "See docs/tools.md > 'Domain configuration'."
)


def load_lexicon():
    """Build {key: {label, kind, patterns}} from domain.json regions + tracts."""
    out = {}
    for kind in ("regions", "tracts"):
        for key, entry in (load_domain(kind) or {}).items():
            if not isinstance(entry, dict):
                continue
            patterns = [
                re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
                for alias in entry.get("aliases", [])
            ]
            out[key] = {
                "label": entry.get("canonical", key),
                "kind": kind,
                "patterns": patterns,
            }
    return out


def find_mentions(body, lexicon):
    """Return dict[region_key -> list of sentence snippets]."""
    sentences = re.split(r"(?<=[.!?])\s+", body)
    out = defaultdict(list)
    for sent in sentences:
        if len(sent) < 20:
            continue
        for key, entry in lexicon.items():
            if any(p.search(sent) for p in entry["patterns"]):
                snippet = sent.strip()
                if len(snippet) > 280:
                    snippet = snippet[:280] + "…"
                out[key].append(snippet)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", help="Focus on a single region/tract key (e.g. M1, CorticospinalTract)")
    ap.add_argument("--save", action="store_true", help="Write atlas-wide report to wiki/syntheses/atlas-anchor.md")
    ap.add_argument("--save-region", action="store_true", help="With --region, write to wiki/concepts/<region>-atlas.md")
    args = ap.parse_args()

    lexicon = load_lexicon()
    if not lexicon:
        sys.exit(DOMAIN_HINT)
    if args.region and args.region not in lexicon:
        sys.exit(f"Unknown region: {args.region}. Available: {', '.join(sorted(lexicon))}")

    sources = load_sources()
    if not sources:
        sys.exit("No sources to scan")

    # region_key -> { source_slug -> [snippets] }
    region_index = defaultdict(lambda: defaultdict(list))
    for s in sources:
        mentions = find_mentions(s["body"], lexicon)
        for key, snippets in mentions.items():
            region_index[key][s["slug"]] = snippets[:3]  # cap snippets per source

    # Single region focus
    if args.region:
        entry = lexicon[args.region]
        sources_hits = region_index.get(args.region, {})
        lines = [
            f"# {entry['label']} — atlas anchor",
            "",
            f"_{len(sources_hits)} sources discuss this {entry['kind'][:-1]}_",
            "",
        ]
        for slug, snippets in sorted(sources_hits.items()):
            lines.append(f"## [[{slug}]]")
            for sn in snippets:
                lines.append(f"> {sn}")
            lines.append("")
        output = "\n".join(lines)

        if args.save_region:
            target = WIKI_DIR / "concepts" / f"{args.region}-atlas.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            header = (
                f"---\ntitle: \"{entry['label']} — atlas anchor\"\n"
                f"type: concept\ntags: [atlas, {entry['kind'][:-1]}]\n"
                f"sources: {sorted(sources_hits)}\n---\n\n"
            )
            target.write_text(header + output + "\n", encoding="utf-8")
            print(f"  ✓ {target.relative_to(REPO_ROOT)}", file=sys.stderr)
        else:
            print(output)
        return

    # Wiki-wide overview
    lines = ["# Brain Atlas Anchor — wiki-wide", ""]
    lines.append(f"Scanned {len(sources)} sources against {len(lexicon)} entries.\n")
    by_kind = {"regions": [], "tracts": []}
    for key, sources_hits in sorted(region_index.items(), key=lambda t: -len(t[1])):
        kind = lexicon[key]["kind"]
        n = len(sources_hits)
        by_kind[kind].append((key, lexicon[key]["label"], n))

    for kind in ("regions", "tracts"):
        lines.append(f"## {kind.capitalize()}")
        lines.append("")
        if not by_kind[kind]:
            lines.append("*(No mentions detected.)*")
        else:
            for key, label, n in by_kind[kind]:
                top = sorted(region_index[key], key=lambda s: -len(region_index[key][s]))[:5]
                top_str = ", ".join(f"[[{s}]]" for s in top)
                lines.append(f"- **{label}** (`{key}`): {n} sources — top: {top_str}")
        lines.append("")

    output = "\n".join(lines)
    if args.save:
        target = WIKI_DIR / "syntheses" / "atlas-anchor.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output + "\n", encoding="utf-8")
        print(f"  ✓ {target.relative_to(REPO_ROOT)}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
