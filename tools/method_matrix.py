#!/usr/bin/env python3
"""Method comparison matrix — tabulate sources × methods or interventions.

For a target outcome or domain, output a Markdown table:

    | Source | Design | N | Methods | Intervention | Year |

Filters by domain, intervention_family, or method. Useful for
methodology chapters and systematic-review prep.

Usage:
    python tools/method_matrix.py                      # all sources
    python tools/method_matrix.py --domain <domain-tag>
    python tools/method_matrix.py --intervention <family>
    python tools/method_matrix.py --method <method>
    python tools/method_matrix.py --save               # writes wiki/syntheses/method-matrix.md
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR, load_sources  # noqa: E402


def filter_sources(sources, domain=None, intervention=None, method=None):
    out = []
    for s in sources:
        fm = s["fm"]
        if domain and domain not in (fm.get("domain") or []):
            continue
        if intervention:
            fam = (fm.get("intervention_family") or "").lower()
            ivs = [str(i).lower() for i in (fm.get("interventions") or [])]
            if intervention.lower() not in [fam] + ivs:
                continue
        if method:
            ms = [str(m).lower() for m in (fm.get("methods") or [])]
            if method.lower() not in ms:
                continue
        out.append(s)
    return out


def render_table(sources):
    rows = []
    rows.append("| Source | Design | N | Population | Methods | Intervention | Year |")
    rows.append("|---|---|---|---|---|---|---|")
    for s in sorted(sources, key=lambda x: (x["fm"].get("year") or 9999, x["slug"])):
        fm = s["fm"]
        slug = s["slug"]
        design = fm.get("study_design") or ""
        n = fm.get("sample_size") or ""
        pop = (fm.get("population") or "").replace("|", "/")[:60]
        methods = ", ".join((fm.get("methods") or [])[:5])
        iv = fm.get("intervention_family") or ", ".join((fm.get("interventions") or [])[:2])
        year = fm.get("year") or ""
        rows.append(f"| [[{slug}]] | {design} | {n} | {pop} | {methods} | {iv} | {year} |")
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", help="Filter by domain tag")
    ap.add_argument("--intervention", help="Filter by intervention family or name")
    ap.add_argument("--method", help="Filter by method")
    ap.add_argument("--save", action="store_true", help="Write to wiki/syntheses/method-matrix.md")
    args = ap.parse_args()

    sources = load_sources()
    if not sources:
        sys.exit("No sources to tabulate")

    sources = filter_sources(
        sources, domain=args.domain, intervention=args.intervention, method=args.method
    )
    if not sources:
        sys.exit("No source matched filters")

    title = "Method Matrix"
    filters = []
    if args.domain:
        filters.append(f"domain={args.domain}")
    if args.intervention:
        filters.append(f"intervention={args.intervention}")
    if args.method:
        filters.append(f"method={args.method}")
    subtitle = " · ".join(filters) if filters else "all sources"

    output = f"# {title} ({subtitle})\n\n{len(sources)} sources\n\n{render_table(sources)}\n"

    if args.save:
        target = WIKI_DIR / "syntheses" / "method-matrix.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
        print(f"  ✓ {target.relative_to(REPO_ROOT)}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
