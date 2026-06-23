#!/usr/bin/env python3
"""Participant cohort tracker — aggregate participant profiles across sources.

Walks `wiki/sources/`, reads `population:` and `sample_size:` from each
source's frontmatter (always available, domain-neutral), plus optional
surface-level descriptor extraction from the body.

The descriptor vocabulary is NOT hardcoded — it is read from
`tools/data/domain.json` (`cohort` section: `chronicity`, `side`, `lesion`
groups, and a `severity_scale`). The shipped default is the neutral
baseline (empty): the tool still reports pooled sample sizes and the
per-intervention breakdown, and simply omits any descriptor group that is
not configured. See `tools/data/domain.stroke.example.json` for a clinical
example.

Usage:
    python tools/cohort_tracker.py
    python tools/cohort_tracker.py --intervention BCI
    python tools/cohort_tracker.py --save
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR, compile_fragments, load_domain, load_sources  # noqa: E402

_COHORT = load_domain("cohort")
# {group_key: {category: compiled regex}} — only groups declared in domain.json
DESCRIPTOR_GROUPS = {
    grp: compile_fragments(_COHORT.get(grp, {}))
    for grp in ("chronicity", "side", "lesion")
    if compile_fragments(_COHORT.get(grp, {}))
}
_SEV = _COHORT.get("severity_scale") or {}
SEVERITY_NAME = _SEV.get("name")
SEVERITY_RE = re.compile(_SEV["regex"], re.I) if _SEV.get("regex") else None


def as_int(val):
    """Coerce a frontmatter sample_size to int, or None if not numeric."""
    if val is None:
        return None
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


def detect(patterns, text):
    return [k for k, p in patterns.items() if p.search(text)]


def extract_severity_range(text):
    if not SEVERITY_RE:
        return None
    m = SEVERITY_RE.search(text)
    if not m or m.lastindex is None or m.lastindex < 2:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    return (min(a, b), max(a, b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervention", help="Filter by intervention family or name")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    sources = load_sources()
    if args.intervention:
        sources = [
            s for s in sources
            if args.intervention.lower() in (
                [str(s["fm"].get("intervention_family") or "").lower()]
                + [str(i).lower() for i in (s["fm"].get("interventions") or [])]
            )
        ]
    if not sources:
        sys.exit("No sources matched")

    n_total = len(sources)
    sample_sizes = [n for n in (as_int(s["fm"].get("sample_size")) for s in sources) if n is not None]
    pooled_n = sum(sample_sizes) if sample_sizes else None

    group_counts = {grp: Counter() for grp in DESCRIPTOR_GROUPS}
    sev_ranges = []
    by_intervention = defaultdict(list)

    for s in sources:
        text = (s["fm"].get("population") or "") + " " + s["body"]
        for grp, patterns in DESCRIPTOR_GROUPS.items():
            for lbl in detect(patterns, text):
                group_counts[grp][lbl] += 1
        sev = extract_severity_range(text)
        if sev:
            sev_ranges.append(sev)
        fam = s["fm"].get("intervention_family") or "(none)"
        by_intervention[fam].append(s)

    lines = ["# Cohort Tracker", ""]
    if args.intervention:
        lines.append(f"_Filter: intervention = `{args.intervention}`_")
        lines.append("")

    lines.append(f"## Aggregate ({n_total} sources)")
    lines.append("")
    lines.append(f"- Pooled sample size (sources reporting N): **{pooled_n}**" if pooled_n else "- Pooled sample size: not reported")
    lines.append("")

    for grp, patterns in DESCRIPTOR_GROUPS.items():
        lines.append(f"### {grp.capitalize()}")
        for k in patterns:  # preserve domain.json declaration order
            lines.append(f"- {k}: {group_counts[grp].get(k, 0)} sources")
        lines.append("")

    if sev_ranges:
        lows = [r[0] for r in sev_ranges]
        highs = [r[1] for r in sev_ranges]
        lines.append(f"### Baseline {SEVERITY_NAME or 'severity'}")
        lines.append(f"- Lowest reported: {min(lows)}–{min(highs)}")
        lines.append(f"- Highest reported: {max(lows)}–{max(highs)}")
        lines.append(f"- Sources reporting a range: {len(sev_ranges)} / {n_total}")
        lines.append("")

    if not args.intervention and len(by_intervention) > 1:
        lines.append("## By intervention family")
        lines.append("")
        for fam, ss in sorted(by_intervention.items(), key=lambda t: -len(t[1])):
            ns = [n for n in (as_int(s["fm"].get("sample_size")) for s in ss) if n is not None]
            pooled = sum(ns) if ns else None
            lines.append(f"- **{fam}**: {len(ss)} sources, pooled N = {pooled if pooled else '?'}")
        lines.append("")

    output = "\n".join(lines)
    if args.save:
        target = WIKI_DIR / "syntheses" / "cohort-tracker.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output + "\n", encoding="utf-8")
        print(f"  ✓ {target.relative_to(REPO_ROOT)}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
