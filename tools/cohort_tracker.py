#!/usr/bin/env python3
"""Patient cohort tracker — aggregate participant profiles across sources.

Walks `wiki/sources/`, reads `population:` and `sample_size:` from each
source's frontmatter, plus surface-level extraction from the body for
the most common stroke-rehab descriptors:

    - chronicity: acute (<7 d) | subacute (7 d–6 mo) | chronic (>6 mo)
    - severity (Fugl-Meyer baseline range when reported)
    - lesion side: left | right | bilateral
    - lesion type: cortical | subcortical | mixed

Outputs a per-cohort summary and per-intervention breakdowns.

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
from _lib import REPO_ROOT, WIKI_DIR, load_sources  # noqa: E402

CHRONICITY_PATTERNS = {
    "chronic": re.compile(r"\bchronic\b|>\s*6\s*month|after\s+6\s*months", re.I),
    "subacute": re.compile(r"\bsubacute\b|1\s*[-to]+\s*6\s*month", re.I),
    "acute": re.compile(r"\bacute\b|<\s*7\s*day|first\s+week", re.I),
}
SIDE_PATTERNS = {
    "left": re.compile(r"\bleft[- ]hemispher|\bLH\b|\bleft hemiparesis", re.I),
    "right": re.compile(r"\bright[- ]hemispher|\bRH\b|\bright hemiparesis", re.I),
    "bilateral": re.compile(r"\bbilateral", re.I),
}
LESION_PATTERNS = {
    "cortical": re.compile(r"\bcortical\b", re.I),
    "subcortical": re.compile(r"\bsubcortical\b|internal\s+capsule|deep\s+stroke", re.I),
}
FM_RE = re.compile(r"Fugl[-\s]?Meyer.{0,40}?(\d{1,2})\s*[-–]\s*(\d{1,2})", re.I)


def detect(patterns, text):
    return [k for k, p in patterns.items() if p.search(text)]


def extract_baseline_fm(text):
    m = FM_RE.search(text)
    if not m:
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
    sample_sizes = [s["fm"].get("sample_size") for s in sources if s["fm"].get("sample_size")]
    pooled_n = sum(sample_sizes) if sample_sizes else None

    chronicity_counts = Counter()
    side_counts = Counter()
    lesion_counts = Counter()
    fm_ranges = []
    by_intervention = defaultdict(list)

    for s in sources:
        text = (s["fm"].get("population") or "") + " " + s["body"]
        for lbl in detect(CHRONICITY_PATTERNS, text):
            chronicity_counts[lbl] += 1
        for lbl in detect(SIDE_PATTERNS, text):
            side_counts[lbl] += 1
        for lbl in detect(LESION_PATTERNS, text):
            lesion_counts[lbl] += 1
        fm = extract_baseline_fm(text)
        if fm:
            fm_ranges.append(fm)
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
    lines.append(f"### Chronicity")
    for k in ("acute", "subacute", "chronic"):
        lines.append(f"- {k}: {chronicity_counts.get(k, 0)} sources")
    lines.append("")
    lines.append("### Lesion side")
    for k in ("left", "right", "bilateral"):
        lines.append(f"- {k}: {side_counts.get(k, 0)} sources")
    lines.append("")
    lines.append("### Lesion type")
    for k in ("cortical", "subcortical"):
        lines.append(f"- {k}: {lesion_counts.get(k, 0)} sources")
    lines.append("")

    if fm_ranges:
        lows = [r[0] for r in fm_ranges]
        highs = [r[1] for r in fm_ranges]
        lines.append("### Baseline Fugl-Meyer Upper Extremity")
        lines.append(f"- Lowest reported: {min(lows)}–{min(highs)}")
        lines.append(f"- Highest reported: {max(lows)}–{max(highs)}")
        lines.append(f"- Sources reporting a range: {len(fm_ranges)} / {n_total}")
        lines.append("")

    if not args.intervention and len(by_intervention) > 1:
        lines.append("## By intervention family")
        lines.append("")
        for fam, ss in sorted(by_intervention.items(), key=lambda t: -len(t[1])):
            ns = [s["fm"].get("sample_size") for s in ss if s["fm"].get("sample_size")]
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
