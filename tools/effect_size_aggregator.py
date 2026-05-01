#!/usr/bin/env python3
"""Effect size aggregator — surface ΔFugl-Meyer / ΔARAT / similar across sources.

Heuristic regex extraction over `wiki/sources/`. Surfaces:

    - Outcome change values (ΔFM, ΔARAT, BBT, MEP amplitude shift)
    - Group context (intervention vs control if labelled)
    - Effect-size keywords (Cohen's d, η², g, p-value)

Output: per-outcome aggregated table, grouped by intervention family.

This is heuristic — meant to surface "look here" candidates for manual
synthesis, not to replace a meta-analysis tool.

Usage:
    python tools/effect_size_aggregator.py
    python tools/effect_size_aggregator.py --outcome FM
    python tools/effect_size_aggregator.py --save
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR, load_sources  # noqa: E402

OUTCOME_PATTERNS = {
    "FM": re.compile(r"(?:Fugl[-\s]?Meyer|FM[A-Z]?[-\s]?(?:UE|LE|U|L)?)\b", re.I),
    "ARAT": re.compile(r"\bARAT\b|Action\s+Research\s+Arm", re.I),
    "BBT": re.compile(r"\bBBT\b|Box\s+(?:and|&)\s+Block", re.I),
    "NHPT": re.compile(r"\bNHPT\b|Nine[-\s]?Hole\s+Peg", re.I),
    "MEP": re.compile(r"\bMEP\s+amplitude|motor\s+evoked\s+potential", re.I),
    "MAS": re.compile(r"\bMAS\b|Modified\s+Ashworth", re.I),
}
DELTA_RE = re.compile(
    r"(?:Δ|\\Delta\s|change|gain|increase|decrease)[^.;\n]{0,40}?([+-]?\d+\.?\d*)\s*(?:points?|pts?)?",
    re.I,
)
COHEN_RE = re.compile(r"(?:Cohen[''']s\s*)?[dgη]\s*[=:]\s*([+-]?\d+\.\d+)", re.I)
PVAL_RE = re.compile(r"\bp\s*[<≤=]\s*(0\.\d+|\.\d+)", re.I)


def find_outcome_mentions(body, outcome_label, pattern):
    """Find each mention of the outcome and pull the surrounding sentence."""
    out = []
    for m in pattern.finditer(body):
        # Take a window around the match (whole sentence boundary if possible)
        start = max(0, body.rfind(".", 0, m.start()) + 1)
        end = body.find(".", m.end())
        if end == -1:
            end = min(len(body), m.end() + 200)
        sentence = body[start:end].strip()
        if len(sentence) > 400:
            sentence = sentence[:400] + "…"
        out.append(sentence)
    return out


def extract_effect(text):
    delta = DELTA_RE.search(text)
    cohen = COHEN_RE.search(text)
    p = PVAL_RE.search(text)
    return {
        "delta": delta.group(1) if delta else None,
        "cohen": cohen.group(1) if cohen else None,
        "p": p.group(1) if p else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outcome", choices=list(OUTCOME_PATTERNS), help="Restrict to one outcome (default: all)")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    sources = load_sources()
    if not sources:
        sys.exit("No sources")

    targets = [args.outcome] if args.outcome else list(OUTCOME_PATTERNS)

    by_outcome = defaultdict(list)  # outcome -> [{slug, intervention, sentence, effect}]
    for s in sources:
        fam = s["fm"].get("intervention_family") or ""
        for outcome in targets:
            for sent in find_outcome_mentions(s["body"], outcome, OUTCOME_PATTERNS[outcome]):
                eff = extract_effect(sent)
                if not (eff["delta"] or eff["cohen"] or eff["p"]):
                    continue
                by_outcome[outcome].append(
                    {"slug": s["slug"], "intervention": fam, "sentence": sent, "effect": eff}
                )

    lines = ["# Effect Size Aggregate", ""]
    if not by_outcome:
        lines.append("*(No quantitative outcome statements detected.)*")
    else:
        for outcome in sorted(by_outcome):
            obs = by_outcome[outcome]
            lines.append(f"## {outcome} ({len(obs)} mentions)")
            lines.append("")
            grouped = defaultdict(list)
            for o in obs:
                grouped[o["intervention"] or "(unspecified)"].append(o)
            for fam, items in sorted(grouped.items(), key=lambda t: -len(t[1])):
                lines.append(f"### Intervention family: {fam}")
                lines.append("")
                for o in items[:10]:
                    eff = o["effect"]
                    parts = []
                    if eff["delta"]:
                        parts.append(f"Δ={eff['delta']}")
                    if eff["cohen"]:
                        parts.append(f"d/g/η={eff['cohen']}")
                    if eff["p"]:
                        parts.append(f"p={eff['p']}")
                    lines.append(f"- [[{o['slug']}]] — {', '.join(parts)}")
                    lines.append(f"  > {o['sentence']}")
                if len(items) > 10:
                    lines.append(f"- … and {len(items) - 10} more")
                lines.append("")

    output = "\n".join(lines)
    if args.save:
        target = WIKI_DIR / "syntheses" / "effect-sizes.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output + "\n", encoding="utf-8")
        print(f"  ✓ {target.relative_to(REPO_ROOT)}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
