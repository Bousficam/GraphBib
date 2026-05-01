#!/usr/bin/env python3
"""DTI metrics aggregator — surface FA / MD / AD / RD reports across the corpus.

For each source whose `methods:` includes `DTI` or `Tractography`, scans
the body for DTI metric mentions:

    - FA (fractional anisotropy)
    - MD (mean diffusivity)
    - AD (axial diffusivity)
    - RD (radial diffusivity)

… and the brain tract or region they qualify (corticospinal, callosum,
arcuate, internal capsule, etc.). Outputs a tract-by-tract aggregate.

Heuristic extraction — surfaces what's reportable; manual curation
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
from _lib import REPO_ROOT, WIKI_DIR, load_sources  # noqa: E402

# DTI metric followed by a number, optionally with ± / ( / ) / mm2/s units
METRIC_RE = re.compile(
    r"\b(FA|MD|AD|RD|fractional\s+anisotropy|mean\s+diffusivity|axial\s+diffusivity|radial\s+diffusivity)"
    r"\s*(?:\(?(?:value|=|:)?\)?\s*)?"
    r"(\d+\.\d+)"
    r"(?:\s*(?:[±+\-]|\+\/-|\+/-)\s*(\d+\.\d+))?",
    re.IGNORECASE,
)
TRACT_PATTERNS = {
    "corticospinal": re.compile(r"corticospinal|\bCST\b|pyramidal\s+tract", re.I),
    "internal_capsule": re.compile(r"internal\s+capsule|\bPLIC\b|posterior\s+limb", re.I),
    "corpus_callosum": re.compile(r"corpus\s+callosum|callosal", re.I),
    "arcuate_fasciculus": re.compile(r"arcuate\s+fasciculus|\bAF\b", re.I),
    "superior_longitudinal_fasciculus": re.compile(r"superior\s+longitudinal|\bSLF\b", re.I),
    "thalamic_radiation": re.compile(r"thalamic\s+radiation|posterior\s+thalamic", re.I),
    "uncinate": re.compile(r"uncinate", re.I),
}

METRIC_NORMALIZE = {
    "fa": "FA",
    "md": "MD",
    "ad": "AD",
    "rd": "RD",
    "fractional anisotropy": "FA",
    "mean diffusivity": "MD",
    "axial diffusivity": "AD",
    "radial diffusivity": "RD",
}


def detect_tract_in_window(text, idx, window=160):
    """Return the tract name detected within ±window characters of idx, if any."""
    lo, hi = max(0, idx - window), min(len(text), idx + window)
    chunk = text[lo:hi]
    for tract, pat in TRACT_PATTERNS.items():
        if pat.search(chunk):
            return tract
    return None


def extract_dti_observations(body):
    """Return list of (tract, metric, value, sd?) tuples."""
    out = []
    for m in METRIC_RE.finditer(body):
        metric_raw = m.group(1).lower().strip()
        metric = METRIC_NORMALIZE.get(metric_raw, metric_raw.upper())
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
        # Sanity: FA in 0–1, MD/AD/RD typically 0.0001–0.005 in mm2/s OR scaled
        if metric == "FA" and not (0 <= val <= 1):
            continue
        tract = detect_tract_in_window(body, m.start())
        out.append((tract, metric, val, sd))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    sources = load_sources()
    dti_sources = [
        s for s in sources
        if any(str(m).upper() in ("DTI", "TRACTOGRAPHY", "DIFFUSION") for m in (s["fm"].get("methods") or []))
    ]
    if not dti_sources:
        sys.exit("No DTI/Tractography sources tagged in frontmatter")

    by_tract = defaultdict(list)  # (tract, metric) -> [(slug, val, sd)]
    no_tract = []
    for s in dti_sources:
        for tract, metric, val, sd in extract_dti_observations(s["body"]):
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
            lines.append(f"## {tract} — {metric}")
            lines.append("")
            lines.append(f"- {len(obs)} observations, range {min(vals):.3f}–{max(vals):.3f}, mean {sum(vals)/len(vals):.3f}")
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
