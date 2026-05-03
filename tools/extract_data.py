#!/usr/bin/env python3
"""Data extraction for systematic reviews — fill an Excel/CSV template
from `wiki/sources/`, with a per-column INSTRUCTIONS row and optional
LLM-driven extraction.

Template structure
==================

Row 1: column headers (e.g. `slug`, `n_intervention`, `risk_of_bias`).
Row 2: an `INSTRUCTIONS` row (slug column = "INSTRUCTIONS"). Each cell
       holds the natural-language extraction rule for that column. This
       row is consumed by the tool, not treated as a data row.
Row 3+: one row per source (slug column = wiki source basename).

Example:

    | slug         | n_intervention                    | primary_delta_fm                                                    | risk_of_bias                                              |
    | INSTRUCTIONS | N participants in the active arm  | Mean ΔFugl-Meyer Upper Extremity at end-of-treatment, ± SD if given | Cochrane RoB 2 overall judgment + main domain of concern  |
    | cervera-2020 |                                   |                                                                     |                                                           |
    | khedr-2005   |                                   |                                                                     |                                                           |

Filling logic (per cell, in order)
==================================

1. **Frontmatter** (deterministic) — known column names map directly to
   YAML fields (title, authors, year, doi, study_design, sample_size,
   population, intervention_family, etc.).
2. **Body regex** (heuristic) — built-in patterns for clinical fields
   (n per arm, age mean, baseline FM, ΔFM, p-value, Cohen's d, CI,
   trial registration ID, …).
3. **LLM extraction** (with `--llm`) — for cells still empty AND with
   a non-empty INSTRUCTIONS, call Claude (via litellm) with the
   instruction + the source body. Cached in `tools/.cache/extract_llm.json`
   so re-runs are nearly free.

Cells already populated by the user are NEVER overwritten.

Modes
=====

    # Pre-fill a NEW template from a source's cites (default SR columns + INSTRUCTIONS row)
    python tools/extract_data.py --from-source cervera-2020 \\
        --output cervera-extraction.xlsx

    # Fill an existing template (frontmatter + regex only)
    python tools/extract_data.py data_extraction.xlsx

    # Same + LLM for cells with instructions still empty
    python tools/extract_data.py data_extraction.xlsx --llm

    # Override the model
    LLM_MODEL=claude-sonnet-4-5 python tools/extract_data.py data.xlsx --llm

Status reported per row: complete / partial / empty / not_found.
Per-cell method tracked in stderr: frontmatter / regex / llm / manual.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, load_sources  # noqa: E402

try:
    from openpyxl import Workbook, load_workbook
    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

CACHE_DIR = REPO_ROOT / "tools" / ".cache"
LLM_CACHE_FILE = CACHE_DIR / "extract_llm.json"

INSTRUCTIONS_MARKER = "INSTRUCTIONS"
DEFAULT_LLM_MODEL = "claude-3-5-sonnet-latest"
LLM_MAX_BODY_CHARS = 60_000   # ~15k tokens
LLM_MAX_TOKENS = 200          # extracted value should be short
LLM_SLEEP_SEC = 0.05          # politeness


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
    "age_sd": [r"age.{0,30}[±+\-]\s*(\d+\.?\d*)"],
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
    "primary_delta_fm": "primary_outcome_delta",
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
    val = BODY_PATTERNS.get(col_norm)
    seen = set()
    while isinstance(val, str):
        if val in seen:
            return None
        seen.add(val)
        val = BODY_PATTERNS.get(val)
    return val


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


# ============================================================================
# LLM extraction (--llm mode)
# ============================================================================

def load_llm_cache():
    if LLM_CACHE_FILE.exists():
        try:
            return json.loads(LLM_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_llm_cache(cache):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LLM_CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def llm_extract(column_name, instruction, body):
    """Single-cell LLM extraction. Returns a string."""
    try:
        from litellm import completion
    except ImportError:
        sys.exit("litellm not installed. Run: pip install litellm")

    body_trim = body[:LLM_MAX_BODY_CHARS]
    truncated = " [body truncated]" if len(body) > LLM_MAX_BODY_CHARS else ""

    prompt = f"""You are extracting one piece of data from a scientific paper for a systematic review.

Field name: {column_name}
Extraction rule: {instruction}

Paper body{truncated}:
---
{body_trim}
---

Output rules:
- Return ONLY the extracted value as plain text (no preamble, no JSON, no quotes).
- Quote numerical values verbatim with units (e.g. "12.4 ± 3.1", "p<0.001").
- If the paper does NOT report this, output exactly: not reported
- Never invent values; never guess.
- Keep the response under 150 characters.
"""

    model = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
    try:
        resp = completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=LLM_MAX_TOKENS,
        )
        value = resp.choices[0].message.content.strip()
        # Strip trivial wrappers
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        time.sleep(LLM_SLEEP_SEC)
        return value
    except Exception as e:
        return f"<llm-error: {type(e).__name__}>"


# ============================================================================
# I/O — XLSX & CSV
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
# Instructions row handling
# ============================================================================

def split_instructions(rows, slug_col):
    """Pop and return the INSTRUCTIONS row if present.

    Returns (instructions_dict_or_None, remaining_data_rows).
    """
    instructions = None
    out = []
    for r in rows:
        slug = str(r.get(slug_col, "")).strip().upper()
        if slug == INSTRUCTIONS_MARKER:
            instructions = {k: ("" if v is None else str(v)) for k, v in r.items()}
            continue
        out.append(r)
    return instructions, out


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
    "slug", "first_author", "year", "journal", "doi",
    "design", "country",
    "n_total", "n_intervention", "n_control",
    "age_mean", "sex_pct_female", "population", "chronicity", "baseline_fm",
    "intervention", "intervention_subfamily",
    "n_sessions", "session_duration_min",
    "primary_outcome_delta", "p_value", "effect_size", "confidence_interval",
    "adverse_events", "trial_registration",
    "risk_of_bias", "notes",
]

DEFAULT_SR_INSTRUCTIONS = {
    "slug": "wiki source page basename (e.g. 'cervera-2020')",
    "first_author": "Family name of the first author only",
    "year": "Publication year (4 digits)",
    "journal": "Full journal name",
    "doi": "DOI in canonical form (e.g. 10.1016/j.neubiorev.2012.10.003)",
    "design": "RCT | cohort | cross-sectional | case-control | case-series | non-randomized trial",
    "country": "Country (or countries, semicolon-separated) where the study was conducted",
    "n_total": "Total N analyzed (post-dropout, intention-to-treat preferred)",
    "n_intervention": "N participants in the active/experimental/intervention arm",
    "n_control": "N participants in the control/sham/placebo arm",
    "age_mean": "Mean age of all participants in years (with SD if reported, e.g. '62.4 ± 11.2')",
    "sex_pct_female": "Percentage of female participants (0–100)",
    "population": "Brief description of the population (e.g. 'chronic stroke patients with moderate hemiparesis, FM-UE 25-50')",
    "chronicity": "Time post-stroke or chronicity category (acute / subacute / chronic), with mean if reported",
    "baseline_fm": "Baseline Fugl-Meyer Upper Extremity score, mean ± SD if reported",
    "intervention": "Principal intervention family (BCI, TMS, tDCS, mirror, robot, mental-practice, physio, combined)",
    "intervention_subfamily": "Specific paradigm (e.g. MI-BCI, AO-BCI, hybrid, rTMS-1Hz, rTMS-10Hz, iTBS, cTBS)",
    "n_sessions": "Total number of intervention sessions",
    "session_duration_min": "Duration per session in minutes",
    "primary_outcome_delta": "Mean change in the PRIMARY outcome from baseline to end-of-treatment, in the intervention arm, with units (verbatim)",
    "p_value": "p-value of the primary between-group comparison (verbatim, e.g. 'p<0.01' or 'p=0.034')",
    "effect_size": "Effect size of primary outcome (Cohen's d, Hedges' g, η², or mean difference with units)",
    "confidence_interval": "95% CI of the primary effect (e.g. '2.1 to 5.4' or '0.32 to 1.07')",
    "adverse_events": "Number of adverse events reported (intervention arm, then control arm), or 'none reported' / 'not reported'",
    "trial_registration": "Trial registration ID (NCT, ISRCTN, EudraCT, CTRI, ChiCTR), or empty if not registered",
    "risk_of_bias": "Cochrane RoB 2 overall judgment (low / some concerns / high) with the main domain of concern (e.g. 'some concerns – blinding of outcome assessor')",
    "notes": "Free-text notes — manual fill",
}


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
    ap.add_argument("--no-instructions", action="store_true",
                    help="With --from-source: skip the INSTRUCTIONS row.")
    ap.add_argument("--slug-column", default="slug",
                    help="Name of the column listing source slugs (default: 'slug').")
    ap.add_argument("--llm", action="store_true",
                    help="Fall back to LLM (litellm) for cells still empty "
                         "after frontmatter + regex, using the INSTRUCTIONS "
                         "row to drive extraction.")
    args = ap.parse_args()

    sources = load_sources()
    if not sources:
        sys.exit("No sources in wiki/sources/")
    sources_index = {s["slug"]: s for s in sources}

    # ---------- Pre-fill mode ----------
    if args.from_source:
        if not args.output:
            sys.exit("--from-source requires --output")
        slugs = slugs_from_cites(args.from_source, sources)
        cols = (args.columns.split(",") if args.columns else DEFAULT_SR_COLUMNS)
        cols = [c.strip() for c in cols]
        if args.slug_column not in cols:
            cols = [args.slug_column] + cols

        rows = []
        if not args.no_instructions:
            instr_row = {c: DEFAULT_SR_INSTRUCTIONS.get(c, "<add your extraction rule here>") for c in cols}
            instr_row[args.slug_column] = INSTRUCTIONS_MARKER
            rows.append(instr_row)
        for slug in slugs:
            row = {c: "" for c in cols}
            row[args.slug_column] = slug
            rows.append(row)

        fmt = detect_format(args.output)
        write_table(args.output, cols, rows, fmt)
        suffix = " (with INSTRUCTIONS row)" if not args.no_instructions else ""
        print(f"  ✓ {args.output} pre-filled with {len(slugs)} slugs from "
              f"{args.from_source}'s cites{suffix}")
        return

    # ---------- Fill mode ----------
    if not args.template:
        sys.exit("Provide a template file (or use --from-source).")
    headers, rows, fmt = read_table(args.template)

    if args.slug_column not in headers:
        sys.exit(f"Template must contain a '{args.slug_column}' column. "
                 f"Got: {headers}")

    instructions, data = split_instructions(rows, args.slug_column)
    if instructions:
        print(f"  · INSTRUCTIONS row detected ({sum(1 for v in instructions.values() if v.strip())} columns annotated)",
              file=sys.stderr)
    elif args.llm:
        print("  ! --llm requested but no INSTRUCTIONS row found. "
              "LLM mode needs per-column rules. Add a row with slug=INSTRUCTIONS.",
              file=sys.stderr)

    llm_cache = load_llm_cache() if args.llm else {}

    payload_cols = [h for h in headers if h != args.slug_column]
    method_count = {"frontmatter": 0, "regex": 0, "llm": 0, "manual": 0, "empty": 0}
    row_status = {"complete": 0, "partial": 0, "empty": 0, "not_found": 0}

    for row in data:
        slug = (str(row.get(args.slug_column) or "")).strip()
        if not slug:
            continue
        src = sources_index.get(slug)
        if not src:
            row_status["not_found"] += 1
            continue

        for col in payload_cols:
            existing = str(row.get(col) or "").strip()
            if existing:
                method_count["manual"] += 1
                continue

            col_norm = normalize_col(col)

            # 1. Frontmatter
            v = apply_fm_map(col_norm, src)
            if v not in (None, ""):
                row[col] = v
                method_count["frontmatter"] += 1
                continue

            # 2. Body regex
            v = extract_from_body(col_norm, src["body"])
            if v not in (None, ""):
                row[col] = v
                method_count["regex"] += 1
                continue

            # 3. LLM (if instruction provided)
            if args.llm and instructions:
                instr = (instructions.get(col) or "").strip()
                if instr and instr != "<add your extraction rule here>":
                    cache_key = f"{slug}::{col_norm}::{hash(instr)}"
                    if cache_key in llm_cache:
                        row[col] = llm_cache[cache_key]
                    else:
                        value = llm_extract(col, instr, src["body"])
                        llm_cache[cache_key] = value
                        row[col] = value
                    if str(row[col] or "").strip().lower() == "not reported":
                        method_count["empty"] += 1
                    else:
                        method_count["llm"] += 1
                    continue

            method_count["empty"] += 1

        # Per-row status
        n_filled = sum(1 for c in payload_cols if str(row.get(c) or "").strip())
        if n_filled == len(payload_cols):
            row_status["complete"] += 1
        elif n_filled > 0:
            row_status["partial"] += 1
        else:
            row_status["empty"] += 1

    if args.llm:
        save_llm_cache(llm_cache)

    out = args.output or args.template
    # Re-include the INSTRUCTIONS row at the top of the output
    final_rows = []
    if instructions:
        final_rows.append(instructions)
    final_rows.extend(data)
    write_table(out, headers, final_rows, fmt)

    print(f"  ✓ {out} updated.")
    print(f"\nPer-row status:")
    for k, v in row_status.items():
        print(f"  {k}: {v}")
    print(f"\nPer-cell method:")
    for k, v in method_count.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
