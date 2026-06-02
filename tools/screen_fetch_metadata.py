#!/usr/bin/env python3
"""Fetch missing metadata AND validate DOIs for each row of `screening/dedup.csv`.

Three passes, each idempotent and cached:

  1. **Abstract cascade**  — PubMed → OpenAlex → Crossref, fills the
     row's title/abstract/journal/doi when missing. (Existing behavior.)

  2. **DOI healing**       — for every row:
        - missing DOI → `crossref_search(title + first_author + year)` →
          set DOI + flag `doi_status=recovered`
        - present DOI → `crossref_validate(doi)` → flag
          `doi_status=valid|invalid`
        - present + valid → cross-check title (SequenceMatcher) and
          year (±1) against Crossref metadata; set `doi_title_match`
          and `doi_year_match`.

  3. **Slug rehab**         — re-derive slugs for rows that came out
     of dedup as `anon-<year>` (missing first-author) but now have a
     valid/recovered DOI. Uses `crossref_slug(doi)` → `<family>-<year>`,
     handles collisions, writes a `slug_renames.csv` audit trail.

Pass 3 is **locked** once `tiab-decisions.xlsx` (or its legacy
.csv) exists for the project — renaming slugs after screening has
started would break the decision trail. The DOI healing pass
still runs; only the slug rewrite is skipped (warnings are logged
so the user can rename manually if they wish).

Cache is shared with all other GraphBib tools via
`tools/.cache/crossref.json` (managed by `tools/crossref.py`).
Re-runs only hit Crossref for new/changed DOIs.

Outputs in `screening/reports/`:
    metadata-log.md     - cascade fetch results
    doi-warnings.md     - per-row DOI hygiene findings (only when issues found)
    slug-renames.csv    - audit trail for slug rehab (only when renames occurred)

Usage:
    python tools/screen_fetch_metadata.py project-review/<vault>/<name>
        # Full run: abstract cascade + DOI healing + slug rehab.

    python tools/screen_fetch_metadata.py project-review/<vault>/<name> --validate-only
        # Skip the abstract cascade, only run DOI healing + slug rehab.
        # Used by /extractor-screen-validate as the gate between
        # /extractor-screen-init and /extractor-screen-tiab.

    python tools/screen_fetch_metadata.py project-review/<vault>/<name> --force
        # Refetch abstracts even when present + re-validate every DOI.

Set CROSSREF_EMAIL (or UNPAYWALL_EMAIL) in env for the polite pool.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent))
from crossref import (  # noqa: E402
    MIN_TITLE_MATCH,
    crossref_metadata,
    crossref_search,
    crossref_slug,
    crossref_validate,
    load_cache,
    normalize_doi,
    save_cache,
    title_similarity,
)
from tabular import read_records, write_records  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
CACHE_DIR = REPO_ROOT / "tools" / ".cache"
# Abstract-fetch cache (independent of the Crossref-only cache that
# crossref.py manages, because abstract bodies are heavier than DOI
# yes/no answers and we want to evict them separately if needed).
CACHE_FILE = CACHE_DIR / "screen_metadata.json"

EMAIL = (
    os.environ.get("UNPAYWALL_EMAIL")
    or os.environ.get("CROSSREF_EMAIL")
    or "graphbib-screening@local"
)

HEADERS = {"User-Agent": f"GraphBib-screening/0.1 (mailto:{EMAIL})"}
TIMEOUT = 20
RETRY_SLEEP = 1.0


def load_abstract_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_abstract_cache(cache):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------
# Abstract-fetch providers (unchanged from before this refactor)

def fetch_pubmed(pmid):
    """Return dict with title, abstract, journal, doi (best-effort)."""
    if not pmid:
        return None
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pubmed&id={pmid}&retmode=xml"
    )
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code != 200 or not r.text:
        return None
    xml = r.text

    def grab(tag, after=""):
        m = re.search(rf"{after}<{tag}[^>]*>(.*?)</{tag}>", xml, re.S)
        return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""

    title = grab("ArticleTitle")
    abs_chunks = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", xml, re.S)
    abstract = " ".join(re.sub(r"<[^>]+>", "", c).strip() for c in abs_chunks)
    journal = grab("Title") or grab("ISOAbbreviation")
    doi_m = re.search(r'<ArticleId IdType="doi">([^<]+)</ArticleId>', xml)
    return {
        "title": title,
        "abstract": abstract,
        "journal": journal,
        "doi": (doi_m.group(1).strip().lower() if doi_m else ""),
        "source": "pubmed",
    }


def _decode_openalex_abstract(inv_index):
    if not inv_index:
        return ""
    words = []
    for w, positions in inv_index.items():
        for p in positions:
            words.append((p, w))
    words.sort()
    return " ".join(w for _, w in words)


def fetch_openalex(doi=None, pmid=None):
    if doi:
        url = f"https://api.openalex.org/works/https://doi.org/{quote(doi, safe='')}"
    elif pmid:
        url = f"https://api.openalex.org/works/pmid:{pmid}"
    else:
        return None
    r = requests.get(url, headers=HEADERS, params={"mailto": EMAIL}, timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    j = r.json()
    return {
        "title": (j.get("title") or "").strip(),
        "abstract": _decode_openalex_abstract(j.get("abstract_inverted_index")),
        "journal": ((j.get("primary_location") or {}).get("source") or {}).get("display_name") or "",
        "doi": ((j.get("doi") or "").replace("https://doi.org/", "").lower()),
        "source": "openalex",
    }


def fetch_crossref(doi):
    if not doi:
        return None
    url = f"https://api.crossref.org/works/{quote(doi, safe='/')}"
    r = requests.get(url, headers=HEADERS, params={"mailto": EMAIL}, timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    m = r.json().get("message", {})
    title = (m.get("title") or [""])[0]
    abstract = m.get("abstract", "") or ""
    abstract = re.sub(r"<[^>]+>", " ", abstract)
    abstract = re.sub(r"\s+", " ", abstract).strip()
    journal = (m.get("container-title") or [""])[0]
    return {
        "title": title.strip(),
        "abstract": abstract,
        "journal": journal.strip(),
        "doi": doi.lower(),
        "source": "crossref",
    }


def fetch_one(rec, cache, force=False):
    """Cascade for missing abstracts. Returns (updated_rec, status_str)."""
    doi = (rec.get("doi") or "").strip().lower()
    pmid = (rec.get("pmid") or "").strip()
    have_abs = bool(rec.get("abstract"))
    if have_abs and not force:
        return rec, "already_had_abstract"

    cache_key = f"doi:{doi}" if doi else (f"pmid:{pmid}" if pmid else None)
    if cache_key and cache_key in cache and not force:
        meta = cache[cache_key]
    else:
        meta = None
        if pmid:
            try:
                meta = fetch_pubmed(pmid)
            except Exception:
                meta = None
            time.sleep(0.34)  # NCBI: 3 req/s without API key
        if not meta or not meta.get("abstract"):
            try:
                m2 = fetch_openalex(doi=doi or None, pmid=pmid or None)
                if m2 and m2.get("abstract"):
                    meta = m2
            except Exception:
                pass
        if (not meta or not meta.get("abstract")) and doi:
            try:
                m3 = fetch_crossref(doi)
                if m3 and (m3.get("abstract") or m3.get("title")):
                    meta = m3 if not meta else {**meta, **{k: v for k, v in m3.items() if v}}
            except Exception:
                pass

        if cache_key:
            cache[cache_key] = meta or {}

    if not meta:
        return rec, "not_found"

    out = dict(rec)
    for k in ("title", "abstract", "journal", "doi"):
        v = (meta.get(k) or "").strip()
        if not v:
            continue
        if force or not (out.get(k) or "").strip():
            out[k] = v
    status = f"fetched_via_{meta.get('source', '?')}"
    if not meta.get("abstract"):
        status += "_no_abstract"
    return out, status


# ----------------------------------------------------------------------
# Pass 2 — DOI healing (recover missing, validate present, cross-check)

def heal_doi(rec, cf_cache):
    """Recover/validate the DOI and cross-check title + year.

    Mutates `rec` in place. Sets these columns on the row:
        doi (possibly recovered)
        doi_status        ∈ {valid, recovered, invalid, unverifiable, missing}
        doi_title_match   ∈ {true, false, ""}
        doi_year_match    ∈ {true, false, ""}

    Returns a list of (level, message) warnings for the report.
    """
    warnings = []
    title = (rec.get("title") or "").strip()
    year = (rec.get("year") or "").strip()
    first_author = (rec.get("first_author") or "").strip()
    doi = normalize_doi(rec.get("doi") or "")
    slug = rec.get("slug", "?")

    if not doi:
        query_bits = [t for t in (title, first_author, year) if t]
        query = " ".join(query_bits).strip()
        if len(query) >= 12:
            recovered = crossref_search(query, cache=cf_cache)
            if recovered:
                rec["doi"] = recovered
                rec["doi_status"] = "recovered"
                doi = recovered
                warnings.append(("info", f"`{slug}`: recovered DOI `{recovered}` via Crossref search."))
            else:
                rec["doi_status"] = "missing"
                warnings.append(("warn", f"`{slug}`: no DOI in CSV and Crossref search returned nothing."))
        else:
            rec["doi_status"] = "missing"
            warnings.append(("warn", f"`{slug}`: too little metadata to recover DOI (title='{title[:60]}', author='{first_author}', year='{year}')."))
    else:
        if crossref_validate(doi, cache=cf_cache):
            rec["doi_status"] = "valid"
        else:
            rec["doi_status"] = "invalid"
            warnings.append(("error", f"`{slug}`: DOI `{doi}` is NOT recognized by Crossref. Likely a malformed or fictitious identifier."))

    if doi and rec["doi_status"] in ("valid", "recovered"):
        md = crossref_metadata(doi, cache=cf_cache)
        if not md:
            rec["doi_status"] = "unverifiable"
            warnings.append(("warn", f"`{slug}`: Crossref returned the DOI but no metadata for cross-check (rare)."))
        else:
            ct = md.get("title", "")
            cy = md.get("year", "")
            if title and ct:
                sim = title_similarity(title, ct)
                if sim >= MIN_TITLE_MATCH:
                    rec["doi_title_match"] = "true"
                else:
                    rec["doi_title_match"] = "false"
                    warnings.append((
                        "error",
                        f"`{slug}`: title mismatch (similarity={sim:.2f}).\n"
                        f"    CSV says    : {title[:100]}\n"
                        f"    Crossref DOI: {ct[:100]}"
                    ))
            if year and cy:
                try:
                    rec["doi_year_match"] = "true" if abs(int(year) - int(cy)) <= 1 else "false"
                    if rec["doi_year_match"] == "false":
                        warnings.append((
                            "warn",
                            f"`{slug}`: year mismatch (CSV={year}, Crossref={cy})."
                        ))
                except ValueError:
                    rec["doi_year_match"] = ""
    return warnings


# ----------------------------------------------------------------------
# Pass 3 — Slug rehab

def rehab_slugs(records, cf_cache):
    """Re-derive `anon-YYYY` slugs from now-valid DOIs.

    Mutates records in place (slug + slug_rehabilitated). Returns a
    list of (old_slug, new_slug, doi) tuples for the audit trail.
    """
    existing_slugs = {r.get("slug") for r in records}
    renames = []

    for r in records:
        slug = r.get("slug", "") or ""
        doi = r.get("doi", "") or ""
        if not slug.startswith("anon-") or not doi:
            continue
        if r.get("doi_status") not in ("valid", "recovered"):
            continue
        new = crossref_slug(doi, cache=cf_cache)
        if not new or new == slug:
            continue

        candidate = new
        n = 1
        while candidate in existing_slugs:
            n += 1
            candidate = f"{new}-{n}"

        existing_slugs.discard(slug)
        existing_slugs.add(candidate)
        r["slug"] = candidate
        r["slug_rehabilitated"] = "true"
        renames.append((slug, candidate, doi))

    return renames


# ----------------------------------------------------------------------
# Reports

def write_doi_warnings(warnings, out_path):
    """Markdown summary, grouped by severity. Skipped when there are no issues."""
    by_level = {"error": [], "warn": [], "info": []}
    for level, msg in warnings:
        by_level.setdefault(level, []).append(msg)
    if not (by_level["error"] or by_level["warn"]):
        # No actionable issues — don't pollute reports/ with an empty file
        if out_path.exists():
            out_path.unlink()
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# DOI hygiene warnings", ""]
    lines.append("This pass cross-checks every DOI against Crossref:")
    lines.append("- recovers missing DOIs via bibliographic search,")
    lines.append("- validates present DOIs against Crossref's agency endpoint,")
    lines.append("- compares Crossref's canonical title + year to the CSV row.")
    lines.append("")
    lines.append(f"**ERROR**: {len(by_level['error'])} — likely wrong-paper or fictitious DOI.")
    lines.append(f"**WARN** : {len(by_level['warn'])} — missing or unverifiable DOI.")
    lines.append(f"**INFO** : {len(by_level['info'])} — DOIs recovered successfully.")
    lines.append("")
    lines.append("Audit each ERROR before running `/extractor-screen-tiab` —")
    lines.append("the screener-tiab agent will auto-default to `uncertain` for any")
    lines.append("row with `doi_title_match=false`, so an audit here saves an")
    lines.append("extra full-text fetch later.")
    lines.append("")
    for level in ("error", "warn", "info"):
        if not by_level[level]:
            continue
        lines.append(f"## {level.upper()}")
        lines.append("")
        for msg in by_level[level]:
            lines.append(f"- {msg}")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return True


def write_slug_renames(renames, out_path):
    if not renames:
        if out_path.exists():
            out_path.unlink()
        return False
    headers = ["old_slug", "new_slug", "doi"]
    records = [{"old_slug": r[0], "new_slug": r[1], "doi": r[2]} for r in renames]
    write_records(records, headers, out_path)
    return True


# ----------------------------------------------------------------------
# CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("project", help="Path to project-review/<vault>/<name>/")
    ap.add_argument("--force", action="store_true",
                    help="Refetch abstracts + re-validate DOIs even when present.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop the abstract cascade after N fetches (smoke-test only — DOI healing still runs on all rows).")
    ap.add_argument("--validate-only", action="store_true",
                    help="Skip the abstract cascade; only run DOI healing + slug rehab.")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    # XLSX is the primary format; the read helper auto-falls-back to
    # the sibling .csv when only the legacy file is present.
    dedup = project / "screening" / "dedup.xlsx"
    if not dedup.exists() and not dedup.with_suffix(".csv").exists():
        sys.exit(f"error: {dedup} (or sibling .csv) not found. Run screen_dedupe.py first.")

    fieldnames, records = read_records(dedup)
    if not records:
        sys.exit(f"error: {dedup} is empty.")

    # Ensure new DOI hygiene columns exist in the header even on
    # legacy dedup.csv files (back-compat for projects that ran
    # screen_dedupe.py before this refactor).
    for col in ("doi_status", "doi_title_match", "doi_year_match", "slug_rehabilitated"):
        if col not in fieldnames:
            fieldnames.append(col)
        for r in records:
            r.setdefault(col, "")

    # ── Pass 1 — abstract cascade ────────────────────────────────────────
    abs_status_counts = {}
    log_lines = ["# Metadata fetch log", ""]
    fetched = 0
    if not args.validate_only:
        abs_cache = load_abstract_cache()
        for r in records:
            if args.limit is not None and fetched >= args.limit:
                break
            before_abs = (r.get("abstract") or "").strip()
            new_rec, status = fetch_one(r, abs_cache, force=args.force)
            r.update(new_rec)
            abs_status_counts[status] = abs_status_counts.get(status, 0) + 1
            if status != "already_had_abstract":
                fetched += 1
                slug = r.get("slug", "?")
                log_lines.append(f"- `{slug}` ({r.get('doi') or r.get('pmid') or 'no-id'}): {status}")
                after_abs = (r.get("abstract") or "").strip()
                if not before_abs and not after_abs:
                    log_lines.append("  - abstract: still empty after cascade")
        save_abstract_cache(abs_cache)

    # ── Pass 2 — DOI healing ─────────────────────────────────────────────
    cf_cache = load_cache()
    doi_warnings = []
    doi_status_counts = {}
    for r in records:
        if args.force:
            # Force re-validation — clear cached flags
            r["doi_status"] = ""
            r["doi_title_match"] = ""
            r["doi_year_match"] = ""
        if r.get("doi_status") and not args.force:
            # Already healed on a previous run — skip the Crossref hit
            doi_status_counts[r["doi_status"]] = doi_status_counts.get(r["doi_status"], 0) + 1
            continue
        warnings = heal_doi(r, cf_cache)
        doi_warnings.extend(warnings)
        doi_status_counts[r.get("doi_status", "")] = doi_status_counts.get(r.get("doi_status", ""), 0) + 1
    save_cache(cf_cache)

    # ── Pass 3 — slug rehab (gated on no existing decisions) ─────────────
    # Slug rehab is LOCKED once T/A decisions have been written —
    # renaming a slug after a decision references it would orphan
    # the decision. Check both formats (xlsx + legacy csv).
    tiab_xlsx = project / "screening" / "tiab-decisions.xlsx"
    tiab_csv = project / "screening" / "tiab-decisions.csv"
    tiab_exists = (tiab_xlsx.exists() and tiab_xlsx.stat().st_size > 0) \
        or (tiab_csv.exists() and tiab_csv.stat().st_size > 0)
    if tiab_exists:
        renames = []
        slug_rehab_status = "locked (tiab-decisions already exists)"
    else:
        renames = rehab_slugs(records, cf_cache)
        save_cache(cf_cache)
        slug_rehab_status = f"ran ({len(renames)} renamed)"

    # ── Write outputs ────────────────────────────────────────────────────
    write_records(records, fieldnames, dedup)

    if not args.validate_only:
        log_path = project / "screening" / "reports" / "metadata-log.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_lines.append("")
        log_lines.append("## Counts")
        for k, v in sorted(abs_status_counts.items()):
            log_lines.append(f"- {k}: {v}")
        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    warnings_path = project / "screening" / "reports" / "doi-warnings.md"
    wrote_warnings = write_doi_warnings(doi_warnings, warnings_path)

    renames_path = project / "screening" / "slug-renames.xlsx"
    wrote_renames = write_slug_renames(renames, renames_path)

    # ── Console summary ──────────────────────────────────────────────────
    print(f"✓ Records       : {len(records)}")
    if not args.validate_only:
        print("  Abstract pass:")
        for k, v in sorted(abs_status_counts.items()):
            print(f"    {k}: {v}")
    print("  DOI healing  :")
    for k, v in sorted(doi_status_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"    {k or '(uncategorized)'}: {v}")
    print(f"  Slug rehab   : {slug_rehab_status}")
    print(f"✓ Wrote         {dedup.relative_to(project.parent)}")
    if wrote_warnings:
        n_err = sum(1 for lvl, _ in doi_warnings if lvl == "error")
        n_warn = sum(1 for lvl, _ in doi_warnings if lvl == "warn")
        print(f"⚠ DOI warnings  {warnings_path.relative_to(project.parent)}"
              f"  ({n_err} errors, {n_warn} warnings — audit before /extractor-screen-tiab)")
    if wrote_renames:
        print(f"✓ Slug renames  {renames_path.relative_to(project.parent)} ({len(renames)} rows)")


if __name__ == "__main__":
    main()
