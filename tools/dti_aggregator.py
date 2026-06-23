#!/usr/bin/env python3
"""DTI metrics aggregator - surface diffusion-metric reports across the corpus.

For each source whose `methods:` includes `DTI` or `Tractography`, scans
the body for diffusion metric mentions (FA / MD / AD / RD or whatever your
domain declares) and the tract / region they qualify. Outputs a
tract-by-tract aggregate.

The metric and tract vocabulary is NOT hardcoded - it is read from
`tools/data/domain.json` (`dti_metrics` and `tracts` sections). The shipped
default is the neutral baseline (empty), so this tool only does something
once a domain pack is configured. See `tools/data/domain.stroke.example.json`
for a neuroimaging example.

Heuristic extraction - surfaces what's reportable; manual curation
recommended before drawing conclusions.

Usage:
    python tools/dti_aggregator.py
    python tools/dti_aggregator.py --save
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR, compile_lexicon, load_domain, load_sources  # noqa: E402

DOMAIN_HINT = (
    "No DTI vocabulary configured. Add a `dti_metrics` (and ideally `tracts`) "
    "section to tools/data/domain.json, or activate the example pack:\n"
    "    cp tools/data/domain.stroke.example.json tools/data/domain.json\n"
    "See docs/tools.md > 'Domain configuration'."
)


def build_metric_matchers():
    """Build (METRIC_RE, METRIC_NORMALIZE) from domain.json `dti_metrics`.

    `dti_metrics` is {canonical: [aliases]}. Returns (None, {}) when empty.
    """
    metrics = load_domain("dti_metrics")  # {canonical: [aliases]}
    normalize = {}
    tokens = []
    for canon, aliases in metrics.items():
        normalize[canon.lower()] = canon
        tokens.append(canon)
        for a in (aliases or []):
            normalize[a.lower()] = canon
            tokens.append(a)
    if not tokens:
        return None, {}
    # escape, then allow flexible whitespace inside multi-word aliases
    alts = sorted({re.escape(t).replace(r"\ ", r"\s+") for t in tokens}, key=len, reverse=True)
    metric_re = re.compile(
        r"\b(" + "|".join(alts) + r")"
        r"\s*(?:\(?(?:value|=|:)?\)?\s*)?"
        r"(\d+\.\d+)"
        r"(?:\s*(?:[±+\-]|\+\/-|\+/-)\s*(\d+\.\d+))?",
        re.IGNORECASE,
    )
    return metric_re, normalize


def detect_tract_in_window(text, idx, tract_lexicon, window=160):
    """Return the tract label detected within ±window characters of idx, if any."""
    lo, hi = max(0, idx - window), min(len(text), idx + window)
    chunk = text[lo:hi]
    for entry in tract_lexicon.values():
        if any(pat.search(chunk) for pat in entry["patterns"]):
            return entry["label"]
    return None


def extract_dti_observations(body, metric_re, normalize, tract_lexicon):
    """Return list of (tract, metric, value, sd?) tuples."""
    out = []
    for m in metric_re.finditer(body):
        metric_raw = m.group(1).lower().strip()
        metric = normalize.get(metric_raw, metric_raw.upper())
        try:
            val = float(m.group(2))
        except ValueError:
            continue
        sd = None
        if m.group(3):
            try:
                sd = float(m.group(3))
            except ValueError:
                pass
        # Sanity: FA in 0-1 (only enforced when the canonical metric is FA)
        if metric == "FA" and not (0 <= val <= 1):
            continue
        tract = detect_tract_in_window(body, m.start(), tract_lexicon)
        out.append((tract, metric, val, sd))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    metric_re, normalize = build_metric_matchers()
    if metric_re is None:
        sys.exit(DOMAIN_HINT)
    tract_lexicon = compile_lexicon(load_domain("tracts"))

    sources = load_sources()
    dti_sources = [
        s for s in sources
        if any(str(m).upper() in ("DTI", "TRACTOGRAPHY", "DIFFUSION") for m in (s["fm"].get("methods") or []))
    ]
    if not dti_sources:
        sys.exit("No DTI/Tractography sources tagged in frontmatter")

    by_tract = defaultdict(list)  # (tract, metric) -> [(slug, val, sd)]
    for s in dti_sources:
        for tract, metric, val, sd in extract_dti_observations(s["body"], metric_re, normalize, tract_lexicon):
            key = (tract or "(unspecified)", metric)
            by_tract[key].append((s["slug"], val, sd))

    lines = ["# DTI Metrics Aggregate", ""]
    lines.append(f"{len(dti_sources)} DTI/Tractography sources scanned.")
    lines.append("")

    if not by_tract:
        lines.append("*(No DTI numeric values detected in the bodies. The agent")
        lines.append("may need to add explicit metric tables to source pages.)*")
    else:
        for (tract, metric), obs in sorted(by_tract.items(), key=lambda t: (t[0][0], t[0][1])):
            vals = [o[1] for o in obs]
            lines.append(f"## {tract} - {metric}")
            lines.append("")
            lines.append(f"- {len(obs)} observations, range {min(vals):.3f}-{max(vals):.3f}, mean {sum(vals)/len(vals):.3f}")
            lines.append("")
            for slug, v, sd in obs[:15]:
                tail = f" ± {sd:.3f}" if sd is not None else ""
                lines.append(f"  - [[{slug}]]: {v:.3f}{tail}")
            if len(obs) > 15:
                lines.append(f"  - … and {len(obs) - 15} more")
            lines.append("")

    output = "\n".join(lines)
    if args.save:
        target = WIKI_DIR / "syntheses" / "dti-aggregate.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output + "\n", encoding="utf-8")
        print(f"  ✓ {target.relative_to(REPO_ROOT)}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
