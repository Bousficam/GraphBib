#!/usr/bin/env python3
"""Render a PRISMA 2020 flowchart from the screening register.

Counts are read deterministically from:
    <project>/screening/identified/*.csv     (sources × records identified)
    <project>/screening/dedup.csv            (records after duplicates removed)
    <project>/screening/tiab-decisions.csv   (decisions on title/abstract)
    <project>/screening/1st-pass/raw/*.pdf   (full-text retrieved)
    <project>/screening/1st-pass/missing.md  (not retrieved — pulled from list)
    <project>/screening/fulltext-decisions.csv (decisions on full text)

Writes a Mermaid flowchart + a tabular summary into:
    <project>/screening/reports/prisma-flowchart.md

The chart follows PRISMA 2020 nomenclature (Identification → Screening →
Eligibility → Included). Re-running overwrites the report; counts are
re-derived from disk every time (idempotent).

Usage:
    python tools/screen_prisma.py project-review/<name>
"""
import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tabular import read_records, write_records  # noqa: E402


def _resolve_table(base, name):
    """Pick the active file for a table — xlsx first, csv fallback.

    base/name should be the stem (no suffix). Returns the Path that
    exists, preferring .xlsx. When neither exists, returns the .xlsx
    path (so callers can check .exists() uniformly).
    """
    xlsx = base / f"{name}.xlsx"
    csv_p = base / f"{name}.csv"
    if xlsx.exists():
        return xlsx
    if csv_p.exists():
        return csv_p
    return xlsx


def count_rows(path):
    """Count data rows in xlsx/csv (excluding header). Returns 0 if absent."""
    if not path.exists():
        return 0
    _, records = read_records(path)
    return len(records)


def count_by_decision(path, col="decision"):
    """Return {decision_value: count} for a table with a `decision` column."""
    if not path.exists():
        return {}
    fieldnames, records = read_records(path)
    if col not in fieldnames:
        return {}
    out = {}
    for row in records:
        v = (str(row.get(col) or "")).strip().lower()
        if v:
            out[v] = out.get(v, 0) + 1
    return out


def count_by_reason(path, decision_value="exclude"):
    """Return [(reason_tag, count), ...] sorted desc for excluded rows.

    Schema-tolerant — the primary exclusion motive is stored under:
      - `reason` for the T/A pass (one-string tag, the screener-tiab
        returns just the criterion tag without verbatim evidence).
      - `tag` for the full-text pass (the screener-fulltext splits
        the triplet into tag / excerpt / location columns).
    When BOTH columns exist (legacy fulltext CSV with a `reason`
    column still around), `tag` wins.
    The PRISMA flowchart counts the PRIMARY motive only — secondary
    motives in `reasons_secondary` are surfaced in the report but
    not double-counted here.
    """
    if not path.exists():
        return []
    _, records = read_records(path)
    reasons = {}
    for row in records:
        if (str(row.get("decision") or "")).strip().lower() != decision_value:
            continue
        primary = (str(row.get("tag") or "")).strip() or (str(row.get("reason") or "")).strip()
        primary = primary or "(no reason given)"
        if ";" in primary:
            primary = primary.split(";", 1)[0].strip()
        reasons[primary] = reasons.get(primary, 0) + 1
    return sorted(reasons.items(), key=lambda kv: -kv[1])


def collect_counts(project: Path):
    identified_dir = project / "screening" / "identified"
    screening = project / "screening"
    dedup = _resolve_table(screening, "dedup")
    tiab = _resolve_table(screening, "tiab-decisions")
    ft = _resolve_table(screening, "fulltext-decisions")
    pdf_dir = screening / "1st-pass" / "raw"
    missing_md = screening / "1st-pass" / "missing.md"

    per_db = {}
    if identified_dir.is_dir():
        # Identified CSVs are user-supplied — accept .csv and .xlsx
        for p in sorted(identified_dir.iterdir()):
            if p.suffix.lower() in (".csv", ".xlsx") and not p.name.startswith("."):
                per_db[p.stem] = count_rows(p)
    n_identified = sum(per_db.values())
    n_dedup = count_rows(dedup)
    n_duplicates = n_identified - n_dedup if n_identified and n_dedup else 0

    tiab_counts = count_by_decision(tiab)
    n_tiab_screened = sum(tiab_counts.values()) if tiab_counts else n_dedup
    n_tiab_excluded = tiab_counts.get("exclude", 0)
    n_tiab_included = tiab_counts.get("include", 0) + tiab_counts.get("uncertain", 0)
    tiab_reasons = count_by_reason(tiab)

    n_pdf_retrieved = len(list(pdf_dir.glob("*.pdf"))) if pdf_dir.is_dir() else 0
    n_pdf_missing = 0
    if missing_md.exists():
        n_pdf_missing = sum(
            1 for line in missing_md.read_text(encoding="utf-8").splitlines()
            if re.match(r"^[-*]\s+", line) and "DOI" not in line[:10].upper()
        )

    ft_counts = count_by_decision(ft)
    n_ft_assessed = sum(ft_counts.values())
    n_ft_excluded = ft_counts.get("exclude", 0)
    n_included = ft_counts.get("include", 0)
    ft_reasons = count_by_reason(ft)

    return {
        "per_db": per_db,
        "identified": n_identified,
        "duplicates": n_duplicates,
        "after_dedup": n_dedup,
        "tiab_screened": n_tiab_screened,
        "tiab_excluded": n_tiab_excluded,
        "tiab_included": n_tiab_included,
        "tiab_reasons": tiab_reasons,
        "ft_retrieved": n_pdf_retrieved,
        "ft_missing": n_pdf_missing,
        "ft_assessed": n_ft_assessed,
        "ft_excluded": n_ft_excluded,
        "ft_reasons": ft_reasons,
        "included": n_included,
    }


def render_mermaid(c):
    """PRISMA 2020 box-style flowchart."""
    per_db = c["per_db"]
    if per_db:
        db_lines = "<br/>".join(f"{name}: n = {n}" for name, n in per_db.items())
        id_text = f"Records identified from:<br/>{db_lines}<br/><b>Total = {c['identified']}</b>"
    else:
        id_text = f"Records identified<br/><b>n = {c['identified']}</b>"

    reason_lines_tiab = "<br/>".join(
        f"{r}: n = {n}" for r, n in c["tiab_reasons"][:5]
    ) or "&nbsp;"
    reason_lines_ft = "<br/>".join(
        f"{r}: n = {n}" for r, n in c["ft_reasons"][:5]
    ) or "&nbsp;"

    return (
        "```mermaid\n"
        "flowchart TD\n"
        f"  ID[\"<b>Identification</b><br/>{id_text}\"]\n"
        f"  DUP[\"Duplicate records removed<br/>n = {c['duplicates']}\"]\n"
        f"  SCR[\"<b>Screening (Title / Abstract)</b><br/>Records screened<br/>n = {c['tiab_screened']}\"]\n"
        f"  XTIAB[\"Records excluded at T/A<br/>n = {c['tiab_excluded']}<br/>{reason_lines_tiab}\"]\n"
        f"  RETR[\"Reports sought for retrieval<br/>n = {c['tiab_included']}\"]\n"
        f"  NOTRETR[\"Reports not retrieved<br/>n = {c['ft_missing']}\"]\n"
        f"  ELIG[\"<b>Eligibility (Full text)</b><br/>Reports assessed<br/>n = {c['ft_assessed']}\"]\n"
        f"  XFT[\"Reports excluded at full text<br/>n = {c['ft_excluded']}<br/>{reason_lines_ft}\"]\n"
        f"  INC[\"<b>Included</b><br/>Studies included in review<br/>n = {c['included']}\"]\n"
        "  ID --> DUP\n"
        "  ID --> SCR\n"
        "  SCR --> XTIAB\n"
        "  SCR --> RETR\n"
        "  RETR --> NOTRETR\n"
        "  RETR --> ELIG\n"
        "  ELIG --> XFT\n"
        "  ELIG --> INC\n"
        "```\n"
    )


def render_table(c):
    rows = [
        ("Records identified (all sources)", c["identified"]),
        ("Duplicate records removed", c["duplicates"]),
        ("Records after dedup", c["after_dedup"]),
        ("Records screened (T/A)", c["tiab_screened"]),
        ("  excluded at T/A", c["tiab_excluded"]),
        ("  included at T/A", c["tiab_included"]),
        ("Full text retrieved", c["ft_retrieved"]),
        ("Full text NOT retrieved", c["ft_missing"]),
        ("Reports assessed for eligibility", c["ft_assessed"]),
        ("  excluded at full text", c["ft_excluded"]),
        ("**Included studies**", f"**{c['included']}**"),
    ]
    out = ["| Stage | n |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in rows]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("project", help="Path to project-review/<name>/")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    if not (project / "screening").is_dir():
        sys.exit(f"error: {project}/screening/ not found.")

    counts = collect_counts(project)
    mermaid = render_mermaid(counts)
    table = render_table(counts)

    out_path = project / "screening" / "reports" / "prisma-flowchart.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    body = (
        "# PRISMA 2020 flowchart\n\n"
        "_Auto-generated by `tools/screen_prisma.py` — re-run after each phase._\n\n"
        "## Flowchart\n\n"
        + mermaid
        + "\n## Summary table\n\n"
        + table
    )
    out_path.write_text(body, encoding="utf-8")

    # Counts also emitted as xlsx for reporting / publication. The
    # markdown above stays — it's the human-readable view; the xlsx
    # is the machine-friendly one (pivots, charts, etc.).
    counts_xlsx = project / "screening" / "reports" / "prisma-counts.xlsx"
    rows = [
        {"phase": "Identified (total)",       "n": counts["identified"]},
        {"phase": "Duplicates removed",       "n": counts["duplicates"]},
        {"phase": "After dedup",              "n": counts["after_dedup"]},
        {"phase": "T/A screened",             "n": counts["tiab_screened"]},
        {"phase": "T/A excluded",             "n": counts["tiab_excluded"]},
        {"phase": "T/A → full-text",          "n": counts["tiab_included"]},
        {"phase": "Reports retrieved (PDF)",  "n": counts["ft_retrieved"]},
        {"phase": "Reports not retrieved",    "n": counts["ft_missing"]},
        {"phase": "Full text assessed",       "n": counts["ft_assessed"]},
        {"phase": "Full text excluded",       "n": counts["ft_excluded"]},
        {"phase": "Included in review",       "n": counts["included"]},
    ]
    # Per-database breakdown of the Identified phase
    for db, n in sorted(counts.get("per_db", {}).items()):
        rows.append({"phase": f"  — from {db}", "n": n})
    # Exclusion reasons
    for tag, n in counts.get("tiab_reasons", []):
        rows.append({"phase": f"T/A exclude · {tag}", "n": n})
    for tag, n in counts.get("ft_reasons", []):
        rows.append({"phase": f"Full-text exclude · {tag}", "n": n})
    write_records(rows, ["phase", "n"], counts_xlsx)

    print(f"✓ Wrote {out_path.relative_to(project.parent)}")
    print(f"✓ Wrote {counts_xlsx.relative_to(project.parent)}")
    print(f"  Identified: {counts['identified']}  →  After dedup: {counts['after_dedup']}")
    print(f"  T/A screened: {counts['tiab_screened']}  →  included {counts['tiab_included']}, excluded {counts['tiab_excluded']}")
    print(f"  Full-text assessed: {counts['ft_assessed']}  →  included {counts['included']}, excluded {counts['ft_excluded']}")


if __name__ == "__main__":
    main()
