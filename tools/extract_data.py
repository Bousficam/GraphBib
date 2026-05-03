#!/usr/bin/env python3
"""Data extraction for systematic reviews — fill an Excel/CSV template
from `wiki/sources/`.

Reads a template (.xlsx or .csv) where:
- Column headers name the fields to extract.
- One column (default: `slug`) lists the source-page basenames to process.

For each row, finds the matching wiki source page, then attempts to
fill each column:
  1. From frontmatter (deterministic) — title, authors, year, journal,
     doi, study_design, sample_size, population, intervention_family,
     interventions, methods, etc.
  2. From regex patterns on the body (heuristic) — n_intervention,
     n_control, age_mean, baseline_fm, primary_outcome_delta, p_value,
     effect_size, cohen_d, confidence_interval, trial_registration, etc.

Cells already populated by the user are preserved (the script never
overwrites your manual edits).

Modes:
    # Fill an existing template
    python tools/extract_data.py data_extraction.xlsx
    python tools/extract_data.py data_extraction.csv --output filled.csv

    # Pre-fill a NEW template from a source's `cites:` (e.g. for a SR)
    python tools/extract_data.py --from-source cervera-2020 \\
        --output cervera-extraction.xlsx

Recognized columns are listed in FM_MAP and BODY_PATTERNS below. Unknown
column headers are left blank — fill them manually.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import load_sources  # noqa: E402

try:
    from openpyxl import Workbook, load_workbook
    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False


# ============================================================================
# Column normalization
# ============================================================================

def normalize_col(col):
    return re.sub(r"[\s\-]+", "_", str(col).lower().strip())


# ============================================================================
# Frontmatter map (deterministic)
# ============================================================================

FM_MAP = {
    "title": "title",
    "authors": lambda s: "; ".join(s["fm"].get("authors") or []),
    "first_author": lambda s: (s["fm"].get("authors") or [""])[0],
    "year": "year",
    "journal": "journal",
    "doi": "doi",
    "design": "study_design",
    "study_design": "study_design",
    "type": "type",
    "sample_size": "sample_size",
    "n": "sample_size",
    "n_total": "sample_size",
    "population": "population",
    "intervention": lambda s: s["fm"].get("intervention_family") or "",
    "intervention_family": "intervention_family",
    "intervention_subfamily": "intervention_subfamily",
    "interventions": lambda s: "; ".join(s["fm"].get("interventions") or []),
    "methods": lambda s: "; ".join(s["fm"].get("methods") or []),
    "domain": lambda s: "; ".join(s["fm"].get("domain") or []),
    "language": "language",
    "peer_reviewed": "peer_reviewed",
    "preprint": "preprint",
    "citation_apa": "citation_apa",
    "bibtex_key": "bibtex_key",
    "ingest_date": "date",
    "source_pdf": "source_pdf",
}


# ============================================================================
# Body regex patterns (heuristic)
# ============================================================================

BODY_PATTERNS = {
    "n_intervention": [
        r"(?:intervention|experimental|active|treatment)\s*(?:group)?\s*[:,]?\s*[Nn]\s*=\s*(\d+)",
        r"(\d+)\s*(?:patients|participants|subjects).{0,40}(?:intervention|experimental|active|treatment)",
    ],
    "n_int": "n_intervention",
    "n_active": "n_intervention",
    "n_experimental": "n_intervention",
    "n_control": [
        r"(?:control|sham|placebo|waitlist)\s*(?:group)?\s*[:,]?\s*[Nn]\s*=\s*(\d+)",
        r"(\d+)\s*(?:patients|participants|subjects).{0,40}(?:control|sham|placebo|waitlist)",
    ],
    "n_ctrl": "n_control",
    "n_sham": "n_control",
    "n_placebo": "n_control",
    "age_mean": [
        r"mean\s*age\s*[=:]?\s*(\d+\.?\d*)",
        r"age\s*(?:was)?\s*[=:]?\s*(\d+\.?\d*)\s*[±+\-]\s*\d+",
        r"age\s*\(M\s*[=:]?\s*(\d+\.?\d*)",
    ],
    "age_sd": [
        r"age.{0,30}[±+\-]\s*(\d+\.?\d*)",
    ],
    "sex_pct_female": [
        r"(\d+\.?\d*)\s*%\s*(?:female|women)",
        r"(?:female|women).{0,10}(\d+\.?\d*)\s*%",
    ],
    "chronicity": [
        r"(chronic|subacute|acute)\s*stroke\s+patients",
        r"(?:time\s+(?:since|post)\s+stroke|chronicity)\s*[=:]?\s*(\d+\.?\d*\s*(?:months?|weeks?|years?))",
    ],
    "baseline_fm": [
        r"(?:baseline|pre[-\s]?intervention|initial).{0,40}Fugl[-\s]?Meyer.{0,30}?(\d+\.?\d*)",
        r"Fugl[-\s]?Meyer.{0,40}(?:baseline|pre[-\s]?intervention).{0,30}?(\d+\.?\d*)",
    ],
    "baseline_fugl_meyer": "baseline_fm",
    "fm_baseline": "baseline_fm",
    "primary_outcome_delta": [
        r"Δ\s*(?:FM|Fugl[-\s]?Meyer)\s*=\s*([+-]?\d+\.?\d*)",
        r"(?:change|gain|increase).{0,50}(?:FM|Fugl[-\s]?Meyer).{0,30}([+-]?\d+\.?\d*)",
    ],
    "delta_fm": "primary_outcome_delta",
    "delta_arat": [
        r"Δ\s*ARAT\s*=\s*([+-]?\d+\.?\d*)",
        r"(?:change|gain).{0,30}ARAT.{0,30}([+-]?\d+\.?\d*)",
    ],
    "p_value": [r"\bp\s*[<≤=]\s*(0?\.\d+|\d+\.\d+)"],
    "p": "p_value",
    "pvalue": "p_value",
    "effect_size": [
        r"(?:Cohen's\s*)?[dgη]\s*[=:]\s*([+-]?\d+\.\d+)",
    ],
    "cohen_d": [
        r"Cohen's\s*d\s*[=:]\s*([+-]?\d+\.\d+)",
        r"\bd\s*[=:]\s*([+-]?\d+\.\d+)",
    ],
    "hedges_g": [
        r"Hedges'?\s*g\s*[=:]\s*([+-]?\d+\.\d+)",
        r"\bg\s*[=:]\s*([+-]?\d+\.\d+)",
    ],
    "confidence_interval": [
        r"95\s*%\s*CI\s*[:\(\[]?\s*([+-]?\d+\.?\d*\s*(?:to|–|-|,)\s*[+-]?\d+\.?\d*)",
    ],
    "ci_95": "confidence_interval",
    "adverse_events": [
        r"(?:adverse events|AE).{0,30}(?:reported|occurred).{0,30}(\d+)",
        r"(no adverse events)",
    ],
    "ae": "adverse_events",
    "trial_registration": [
        r"\b(NCT\d{8})\b",
        r"\b(ISRCTN\d+)\b",
        r"\b(CTRI/\d{4}/\d+/\d+)\b",
        r"\b(EudraCT\s*\d{4}-\d{6}-\d{2})\b",
    ],
    "trial_id": "trial_registration",
    "country": [
        r"(?:was|were)\s+(?:conducted|recruited|performed)\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ],
    "n_sessions": [
        r"(\d+)\s+sessions",
        r"(\d+)\s+training\s+sessions",
    ],
    "session_duration_min": [
        r"(\d+)\s*[-–]?\s*(?:min|minute)\s+(?:long\s+)?sessions",
    ],
}


def resolve_pattern(col_norm):
    """Follow alias chains in BODY_PATTERNS until reaching a list of regexes."""
    val = BODY_PATTERNS.get(col_norm)
    seen = set()
    while isinstance(val, str):
        if val in seen:
            return None
        seen.add(val)
        val = BODY_PATTERNS.get(val)
    return val


# ============================================================================
# Extraction
# ============================================================================

def apply_fm_map(col_norm, source):
    spec = FM_MAP.get(col_norm)
    if spec is None:
        return None
    if callable(spec):
        return spec(source)
    val = source["fm"].get(spec)
    if isinstance(val, list):
        return "; ".join(str(v) for v in val)
    return val if val is not None else ""


def extract_from_body(col_norm, body):
    patterns = resolve_pattern(col_norm)
    if not patterns:
        return None
    for pat in patterns:
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            return m.group(1) if m.groups() else m.group(0)
    return ""


def extract_for_source(source, columns, slug_col):
    out = {}
    for col in columns:
        if col == slug_col:
            continue
        col_norm = normalize_col(col)
        v = apply_fm_map(col_norm, source)
        if v is None:
            v = extract_from_body(col_norm, source["body"])
        if v is None:
            v = ""
        out[col] = v
    return out


# ============================================================================
# I/O
# ============================================================================

def detect_format(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".xlsx":
        return "xlsx"
    if suffix == ".csv":
        return "csv"
    sys.exit(f"Unsupported format: {suffix}. Use .xlsx or .csv.")


def read_table(path):
    fmt = detect_format(path)
    if fmt == "xlsx":
        if not HAS_XLSX:
            sys.exit("openpyxl not installed. Run: pip install openpyxl")
        wb = load_workbook(path)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            sys.exit(f"Empty workbook: {path}")
        headers = [str(h) if h is not None else "" for h in rows[0]]
        data = []
        for r in rows[1:]:
            data.append({h: ("" if v is None else v) for h, v in zip(headers, r)})
        return headers, data, fmt
    # csv
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        data = list(reader)
    return headers, data, fmt


def write_table(path, headers, data, fmt):
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        for row in data:
            ws.append([row.get(h, "") for h in headers])
        wb.save(path)
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in data:
                writer.writerow({h: row.get(h, "") for h in headers})


# ============================================================================
# --from-source helper
# ============================================================================

def slugs_from_cites(source_slug, sources):
    src = next((s for s in sources if s["slug"] == source_slug), None)
    if not src:
        sys.exit(f"Source not found: {source_slug}")
    cited = {str(d).lower() for d in (src["fm"].get("cites") or [])}
    out = []
    for s in sources:
        d = (s["fm"].get("doi") or "").strip().lower()
        if d and d in cited:
            out.append(s["slug"])
    return sorted(out)


DEFAULT_SR_COLUMNS = [
    "slug",
    "first_author",
    "year",
    "journal",
    "doi",
    "design",
    "country",
    "n_total",
    "n_intervention",
    "n_control",
    "age_mean",
    "sex_pct_female",
    "population",
    "chronicity",
    "baseline_fm",
    "intervention",
    "intervention_subfamily",
    "n_sessions",
    "session_duration_min",
    "primary_outcome_delta",
    "p_value",
    "effect_size",
    "confidence_interval",
    "adverse_events",
    "trial_registration",
    "risk_of_bias",
    "notes",
]


# ============================================================================
# Main
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("template", nargs="?",
                    help="Excel (.xlsx) or CSV template to populate.")
    ap.add_argument("--output", "-o",
                    help="Write to this path (default: overwrite input).")
    ap.add_argument("--from-source",
                    help="Pre-fill a NEW template from a source's cites: "
                         "(use with --output).")
    ap.add_argument("--columns",
                    help="Comma-separated column names for --from-source "
                         "(default: a sensible SR set).")
    ap.add_argument("--slug-column", default="slug",
                    help="Name of the column listing source slugs (default: 'slug').")
    args = ap.parse_args()

    sources = load_sources()
    if not sources:
        sys.exit("No sources in wiki/sources/")
    sources_index = {s["slug"]: s for s in sources}

    # Pre-fill mode
    if args.from_source:
        if not args.output:
            sys.exit("--from-source requires --output")
        slugs = slugs_from_cites(args.from_source, sources)
        cols = (args.columns.split(",") if args.columns else DEFAULT_SR_COLUMNS)
        cols = [c.strip() for c in cols]
        if args.slug_column not in cols:
            cols = [args.slug_column] + cols
        data = [{c: "" for c in cols} for _ in slugs]
        for row, slug in zip(data, slugs):
            row[args.slug_column] = slug
        fmt = detect_format(args.output)
        write_table(args.output, cols, data, fmt)
        print(f"  ✓ {args.output} pre-filled with {len(slugs)} slugs from "
              f"{args.from_source}'s cites:")
        return

    # Extract mode
    if not args.template:
        sys.exit("Provide a template file (or use --from-source).")
    headers, data, fmt = read_table(args.template)

    if args.slug_column not in headers:
        sys.exit(f"Template must contain a '{args.slug_column}' column. "
                 f"Got: {headers}")

    stats = {"complete": 0, "partial": 0, "empty": 0, "not_found": 0}
    payload_cols = [h for h in headers if h != args.slug_column]

    for row in data:
        slug = (str(row.get(args.slug_column) or "")).strip()
        if not slug:
            continue
        src = sources_index.get(slug)
        if not src:
            stats["not_found"] += 1
            continue
        extracted = extract_for_source(src, headers, args.slug_column)
        # Only fill empty cells (don't overwrite manual edits)
        n_already = sum(1 for c in payload_cols if str(row.get(c) or "").strip())
        for c, v in extracted.items():
            if not str(row.get(c) or "").strip():
                row[c] = v
        n_filled_after = sum(1 for c in payload_cols if str(row.get(c) or "").strip())
        if n_filled_after == len(payload_cols):
            stats["complete"] += 1
        elif n_filled_after > 0:
            stats["partial"] += 1
        else:
            stats["empty"] += 1

    out = args.output or args.template
    write_table(out, headers, data, fmt)

    print(f"  ✓ {out} updated.")
    print(f"  complete: {stats['complete']}")
    print(f"  partial:  {stats['partial']}")
    print(f"  empty:    {stats['empty']}")
    print(f"  not found in wiki: {stats['not_found']}")


if __name__ == "__main__":
    main()
