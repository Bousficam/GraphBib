#!/usr/bin/env python3
"""Replication tracker — chain replications, flag single-study claims.

Walks `wiki/sources/`. Uses the `replication_of: "<DOI>"` frontmatter
field to build replication chains across the corpus. Outputs:

    1. Replication chains: original → replication(s), with consistency
       flag if both pages mention the outcome.
    2. Single-study concept claims: concept pages whose `## Empirical
       Evidence` rests on a single source.
    3. Replication candidates: pairs of papers with high methodological
       similarity (same intervention + similar population) that are not
       declared replications — worth checking.

Usage:
    python tools/replication_tracker.py
    python tools/replication_tracker.py --save
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR, WIKILINK_RE, load_sources, section  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    sources = load_sources()
    if not sources:
        sys.exit("No sources")

    # Index DOI -> slug
    doi_to_slug = {}
    for s in sources:
        d = (s["fm"].get("doi") or "").strip().lower()
        if d:
            doi_to_slug[d] = s["slug"]

    # 1. Replication chains
    chains = defaultdict(list)  # original_slug -> [replicating_slug]
    declared = []
    for s in sources:
        rof = (s["fm"].get("replication_of") or "").strip().lower()
        if not rof:
            continue
        if rof in doi_to_slug:
            chains[doi_to_slug[rof]].append(s["slug"])
        else:
            declared.append((s["slug"], rof, "original-not-in-wiki"))

    # 2. Single-study concept claims
    concepts_dir = WIKI_DIR / "concepts"
    single_study = []
    if concepts_dir.is_dir():
        for cp in sorted(concepts_dir.glob("*.md")):
            text = cp.read_text(encoding="utf-8")
            ev = section(text, "Empirical Evidence")
            if not ev:
                continue
            cited = set(WIKILINK_RE.findall(ev))
            in_wiki_sources = {sl for sl in cited if any(s["slug"] == sl for s in sources)}
            if len(in_wiki_sources) == 1:
                single_study.append((cp.stem, list(in_wiki_sources)[0]))

    # 3. Replication candidates: same intervention_family + similar population
    by_iv = defaultdict(list)
    for s in sources:
        fam = (s["fm"].get("intervention_family") or "").strip().lower()
        if fam and fam != "none":
            by_iv[fam].append(s)

    candidates = []
    for fam, items in by_iv.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                # Skip if already declared
                a_doi = (a["fm"].get("doi") or "").strip().lower()
                b_doi = (b["fm"].get("doi") or "").strip().lower()
                a_repl = (a["fm"].get("replication_of") or "").strip().lower()
                b_repl = (b["fm"].get("replication_of") or "").strip().lower()
                if a_repl == b_doi or b_repl == a_doi:
                    continue
                # Heuristic similarity: same study_design + close population
                if (a["fm"].get("study_design") or "") != (b["fm"].get("study_design") or ""):
                    continue
                pop_a = (a["fm"].get("population") or "").lower()
                pop_b = (b["fm"].get("population") or "").lower()
                if not pop_a or not pop_b:
                    continue
                # Token overlap
                ta = set(pop_a.split())
                tb = set(pop_b.split())
                if not ta or not tb:
                    continue
                overlap = len(ta & tb) / min(len(ta), len(tb))
                if overlap >= 0.4:
                    candidates.append((fam, a["slug"], b["slug"], round(overlap, 2)))

    lines = ["# Replication Tracker", ""]

    lines.append("## Declared replication chains")
    lines.append("")
    if not chains and not declared:
        lines.append("*(No `replication_of:` field set in any source.)*")
    else:
        for orig, repls in sorted(chains.items()):
            lines.append(f"- **[[{orig}]]** ← replicated by:")
            for r in repls:
                lines.append(f"  - [[{r}]]")
        for slug, doi, status in declared:
            lines.append(f"- [[{slug}]] declares replication of `{doi}` ({status})")
    lines.append("")

    lines.append("## Concept pages with single-study Empirical Evidence")
    lines.append("")
    if not single_study:
        lines.append("*(All concept pages with empirical evidence cite multiple sources, or empirical sections are empty.)*")
    else:
        for cname, src in single_study:
            lines.append(f"- [[{cname}]] rests on [[{src}]]")
    lines.append("")

    lines.append("## Replication candidates (same intervention family + similar population)")
    lines.append("")
    if not candidates:
        lines.append("*(No candidate pairs surfaced.)*")
    else:
        candidates.sort(key=lambda t: (-t[3], t[0]))
        for fam, a, b, ov in candidates[:30]:
            lines.append(f"- **{fam}** — [[{a}]] ↔ [[{b}]] (population overlap = {ov})")
    lines.append("")

    output = "\n".join(lines)
    if args.save:
        target = WIKI_DIR / "syntheses" / "replication-tracker.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output + "\n", encoding="utf-8")
        print(f"  ✓ {target.relative_to(REPO_ROOT)}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
