#!/usr/bin/env python3
"""Detect suspected dataset overlap across included articles.

After the full-text pass, every `decision=include` row carries
harvested metadata (sites, recruitment window, team, N, trial
registration ID) in the `metadata_json` column. This script
clusters the includes by overlap likelihood and writes a report
the orchestrator surfaces in Phase 4b of /extractor-screen-fulltext
(audit gate before staging includes into extraction/).

Clustering signals (any one fires a candidate pair):

  1. **Same trial registration ID** — strongest signal. If two
     papers report the same NCT/ChiCTR/EudraCT ID, they are by
     definition reporting on the same trial. → cluster confidence
     HIGH.

  2. **Same senior author / lab** AND recruitment windows overlap
     by ≥ 50% AND N within ±20% → cluster confidence MEDIUM.
     (Authors reuse cohorts.)

  3. **Site overlap** (≥ 1 shared named site) AND recruitment
     windows overlap by ≥ 50% → cluster confidence LOW.
     (Two groups can recruit from the same hospital independently.)

Each cluster is reported with all matching papers, the signal that
fired, and a recommended action (keep-both / pick-one / merge —
the user decides at the audit gate).

Usage:
    python tools/screen_overlap.py project-review/<vault>/<name>

Reads:
    screening/fulltext-decisions.csv   (decision + metadata_json)

Writes:
    screening/reports/overlap-clusters.md   (suspected clusters)
    screening/overlap-decisions.csv         (audit trail; empty
                                              until user fills it)
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


# Thresholds (tunable)
N_TOLERANCE = 0.20            # ±20% on N
WINDOW_OVERLAP_THRESHOLD = 0.5  # ≥ 50% time-window overlap


# ----------------------------------------------------------------------
# Date helpers

def parse_yyyymm(s):
    """Return a year × 12 + month integer, or None."""
    if not s:
        return None
    s = s.strip()
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?$", s)
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else 6  # mid-year default
    return year * 12 + month


def window_overlap(start_a, end_a, start_b, end_b):
    """Return overlap fraction of the SHORTER window. 0..1."""
    if None in (start_a, end_a, start_b, end_b):
        return 0.0
    lo = max(start_a, start_b)
    hi = min(end_a, end_b)
    overlap = max(0, hi - lo + 1)
    span_a = max(1, end_a - start_a + 1)
    span_b = max(1, end_b - start_b + 1)
    return overlap / min(span_a, span_b)


def parse_n(s):
    """Parse N — integer or 'min-max' range. Returns (min, max) or (None, None)."""
    if not s:
        return None, None
    s = str(s).strip()
    if "-" in s:
        parts = s.split("-", 1)
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None, None
    try:
        n = int(s)
        return n, n
    except ValueError:
        return None, None


def n_within_tolerance(n_a, n_b, tol=N_TOLERANCE):
    """Return True when the two N intervals overlap or are within ±tol of each other."""
    a_min, a_max = parse_n(n_a)
    b_min, b_max = parse_n(n_b)
    if None in (a_min, b_min):
        return False
    # Use centers for tolerance check
    a_mid = (a_min + a_max) / 2
    b_mid = (b_min + b_max) / 2
    ref = max(a_mid, b_mid) or 1
    return abs(a_mid - b_mid) / ref <= tol


# ----------------------------------------------------------------------
# Metadata extraction

def normalize_token(s):
    """Lowercase, strip punctuation, collapse whitespace — for set comparisons."""
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def load_includes(decisions_csv):
    """Return list[dict] of include rows enriched with parsed metadata."""
    if not decisions_csv.exists():
        return []
    rows = []
    with open(decisions_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if (r.get("decision") or "").strip().lower() != "include":
                continue
            md_raw = (r.get("metadata_json") or "").strip()
            md = {}
            if md_raw:
                try:
                    md = json.loads(md_raw)
                except json.JSONDecodeError:
                    md = {}
            rows.append({
                "slug": r.get("slug", "?"),
                "doi": r.get("doi", ""),
                "title": r.get("title", "")[:120],
                "sites": [normalize_token(s) for s in (md.get("sites") or []) if s],
                "team": [normalize_token(t) for t in (md.get("team") or []) if t],
                "n": (md.get("n") or "").strip(),
                "registration": normalize_token(md.get("registration") or ""),
                "recruitment_start": parse_yyyymm(md.get("recruitment_start") or ""),
                "recruitment_end": parse_yyyymm(md.get("recruitment_end") or ""),
                "_md_raw": md_raw,
            })
    return rows


# ----------------------------------------------------------------------
# Pairwise checks

def pair_signal(a, b):
    """Return (confidence, signal_label, evidence) or None when no overlap."""
    # 1. Same registration ID — strongest
    if a["registration"] and a["registration"] == b["registration"]:
        return ("HIGH", "same-trial-registration", a["registration"])

    win_overlap = window_overlap(
        a["recruitment_start"], a["recruitment_end"],
        b["recruitment_start"], b["recruitment_end"],
    )
    n_match = n_within_tolerance(a["n"], b["n"])

    # 2. Same senior/lab AND window overlap AND N close
    if a["team"] and b["team"]:
        shared_team = set(a["team"]) & set(b["team"])
        if shared_team and win_overlap >= WINDOW_OVERLAP_THRESHOLD and n_match:
            return ("MEDIUM", "same-team-overlapping-window-similar-n",
                    f"team={','.join(sorted(shared_team))}, window={win_overlap:.0%}, n=({a['n']} vs {b['n']})")

    # 3. Site overlap AND window overlap
    if a["sites"] and b["sites"]:
        shared_sites = set(a["sites"]) & set(b["sites"])
        if shared_sites and win_overlap >= WINDOW_OVERLAP_THRESHOLD:
            return ("LOW", "shared-site-overlapping-window",
                    f"sites={','.join(sorted(shared_sites))[:80]}, window={win_overlap:.0%}")

    return None


def cluster_includes(rows):
    """Return list[dict] — one entry per detected cluster."""
    clusters = []
    visited = set()  # set of frozenset({slug_a, slug_b}) already reported
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            key = frozenset({a["slug"], b["slug"]})
            if key in visited:
                continue
            sig = pair_signal(a, b)
            if not sig:
                continue
            confidence, label, evidence = sig
            visited.add(key)
            clusters.append({
                "confidence": confidence,
                "signal": label,
                "evidence": evidence,
                "slug_a": a["slug"],
                "slug_b": b["slug"],
                "doi_a": a["doi"],
                "doi_b": b["doi"],
                "title_a": a["title"],
                "title_b": b["title"],
            })
    # Sort: HIGH first, then MEDIUM, then LOW
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    clusters.sort(key=lambda c: (rank.get(c["confidence"], 9), c["slug_a"], c["slug_b"]))
    return clusters


# ----------------------------------------------------------------------
# Output

def write_clusters_md(clusters, out_path, n_includes):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Suspected dataset overlap among includes",
        "",
        f"Scanned **{n_includes} included articles** for shared trial",
        "registrations, recruitment cohorts, or sites. Each pair below",
        "is a CANDIDATE — the user resolves at the audit gate of",
        "`/extractor-screen-fulltext` (Phase 4b).",
        "",
        "## Signals + confidence",
        "",
        "| Signal                            | Confidence | What it suggests                              |",
        "|---|---|---|",
        "| `same-trial-registration`         | HIGH       | Same registered trial — same patients.        |",
        "| `same-team-overlapping-window-similar-n` | MEDIUM | Likely cohort reuse by the same group.        |",
        "| `shared-site-overlapping-window`  | LOW        | Two groups recruiting from the same hospital. |",
        "",
    ]
    if not clusters:
        lines.append("**No overlap signals detected.** All includes appear to come "
                     "from distinct cohorts. (Caveat: this only catches what the "
                     "screener-fulltext managed to harvest from the body — sparse "
                     "metadata cannot be cross-checked.)")
        lines.append("")
    else:
        for c in clusters:
            lines.append(f"## {c['slug_a']} ↔ {c['slug_b']}  ({c['confidence']})")
            lines.append("")
            lines.append(f"- **Signal**: `{c['signal']}`")
            lines.append(f"- **Evidence**: {c['evidence']}")
            lines.append(f"- **{c['slug_a']}** — `{c['doi_a']}` — {c['title_a']}")
            lines.append(f"- **{c['slug_b']}** — `{c['doi_b']}` — {c['title_b']}")
            lines.append("- **User action** [keep-both / pick-one / merge-into-one]:")
            lines.append("    _Leave bracketed action above; resolved during"
                         " /extractor-screen-fulltext Phase 4b._")
            lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_decisions_stub(clusters, out_path):
    """Empty audit-trail CSV. The orchestrator's audit gate fills it."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["pair", "confidence", "signal", "evidence",
            "slug_a", "slug_b", "user_action", "rationale", "timestamp"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for c in clusters:
            w.writerow({
                "pair": f"{c['slug_a']}|{c['slug_b']}",
                "confidence": c["confidence"],
                "signal": c["signal"],
                "evidence": c["evidence"],
                "slug_a": c["slug_a"],
                "slug_b": c["slug_b"],
                "user_action": "",
                "rationale": "",
                "timestamp": "",
            })


# ----------------------------------------------------------------------
# CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("project", help="Path to project-review/<vault>/<name>/")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    decisions = project / "screening" / "fulltext-decisions.csv"
    if not decisions.exists():
        sys.exit(f"error: {decisions} not found. Run /extractor-screen-fulltext first.")

    rows = load_includes(decisions)
    if not rows:
        sys.exit(f"error: no `decision=include` rows in {decisions}.")

    clusters = cluster_includes(rows)

    md_path = project / "screening" / "reports" / "overlap-clusters.md"
    csv_path = project / "screening" / "overlap-decisions.csv"
    write_clusters_md(clusters, md_path, n_includes=len(rows))
    write_decisions_stub(clusters, csv_path)

    print(f"✓ Includes scanned : {len(rows)}")
    print(f"✓ Clusters         : {len(clusters)}")
    bucket = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for c in clusters:
        bucket[c["confidence"]] = bucket.get(c["confidence"], 0) + 1
    for k in ("HIGH", "MEDIUM", "LOW"):
        if bucket[k]:
            print(f"    {k}: {bucket[k]}")
    print(f"✓ Report           : {md_path.relative_to(project.parent)}")
    print(f"✓ Audit trail stub : {csv_path.relative_to(project.parent)}")
    if clusters:
        print()
        print("Next: review the clusters at the Phase 4b audit gate of "
              "/extractor-screen-fulltext.")


if __name__ == "__main__":
    main()
