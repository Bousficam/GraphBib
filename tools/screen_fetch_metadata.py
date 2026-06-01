#!/usr/bin/env python3
"""Fetch missing title + abstract for each row of `screening/dedup.csv`.

Cascade per record (stops at first success):
    1. PubMed E-utilities (efetch) — when PMID is known.
    2. OpenAlex                  — when DOI is known (or PMID -> DOI lookup).
    3. Crossref                  — when DOI is known.

Only records whose abstract is empty are queried. Existing abstracts
are preserved verbatim. Title is upgraded only when missing.

Writes back into the same `dedup.csv` and appends a per-DOI status to
`screening/reports/metadata-log.md`.

Usage:
    python tools/screen_fetch_metadata.py project-review/<name>
    python tools/screen_fetch_metadata.py project-review/<name> --force
        # --force: refetch even when abstract is already present.

Set UNPAYWALL_EMAIL or CROSSREF_EMAIL in env to identify your client
(polite pool — recommended by the providers).

Cached in tools/.cache/screen_metadata.json (keyed by doi|pmid).
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

REPO_ROOT = Path(__file__).parent.parent
CACHE_DIR = REPO_ROOT / "tools" / ".cache"
CACHE_FILE = CACHE_DIR / "screen_metadata.json"

EMAIL = (
    os.environ.get("UNPAYWALL_EMAIL")
    or os.environ.get("CROSSREF_EMAIL")
    or "graphbib-screening@local"
)

HEADERS = {"User-Agent": f"GraphBib-screening/0.1 (mailto:{EMAIL})"}
TIMEOUT = 20
RETRY_SLEEP = 1.0


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------
# Providers

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
        # Tolerant of attributes on the opening tag.
        m = re.search(
            rf"{after}<{tag}[^>]*>(.*?)</{tag}>", xml, re.S
        )
        return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""

    title = grab("ArticleTitle")
    abs_chunks = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", xml, re.S)
    abstract = " ".join(re.sub(r"<[^>]+>", "", c).strip() for c in abs_chunks)
    journal = grab("Title") or grab("ISOAbbreviation")
    doi_m = re.search(
        r'<ArticleId IdType="doi">([^<]+)</ArticleId>', xml
    )
    return {
        "title": title,
        "abstract": abstract,
        "journal": journal,
        "doi": (doi_m.group(1).strip().lower() if doi_m else ""),
        "source": "pubmed",
    }


def _decode_openalex_abstract(inv_index):
    """OpenAlex stores abstracts as {word: [positions]}."""
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
    """Try the cascade. Return (updated_rec, status_str)."""
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
        # 1. PubMed
        if pmid:
            try:
                meta = fetch_pubmed(pmid)
            except Exception:
                meta = None
            time.sleep(0.34)  # NCBI: max 3 req/s without API key
        # 2. OpenAlex
        if not meta or not meta.get("abstract"):
            try:
                m2 = fetch_openalex(doi=doi or None, pmid=pmid or None)
                if m2 and m2.get("abstract"):
                    meta = m2
            except Exception:
                pass
        # 3. Crossref
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

    # Merge — never overwrite non-empty user fields unless --force
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
# CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("project", help="Path to project-review/<name>/")
    ap.add_argument("--force", action="store_true",
                    help="Refetch even when abstract is present (overwrites).")
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop after N fetches (for smoke-test).")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    dedup = project / "screening" / "dedup.csv"
    if not dedup.exists():
        sys.exit(f"error: {dedup} not found. Run screen_dedupe.py first.")

    with open(dedup, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        records = list(reader)

    cache = load_cache()
    status_counts = {}
    log_lines = ["# Metadata fetch log", ""]
    fetched = 0
    for r in records:
        if args.limit is not None and fetched >= args.limit:
            break
        before_abs = (r.get("abstract") or "").strip()
        new_rec, status = fetch_one(r, cache, force=args.force)
        r.update(new_rec)
        status_counts[status] = status_counts.get(status, 0) + 1
        if status != "already_had_abstract":
            fetched += 1
            slug = r.get("slug", "?")
            log_lines.append(f"- `{slug}` ({r.get('doi') or r.get('pmid') or 'no-id'}): {status}")
            after_abs = (r.get("abstract") or "").strip()
            if not before_abs and not after_abs:
                log_lines.append("  - abstract: still empty after cascade")

    save_cache(cache)

    with open(dedup, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(records)

    log_path = project / "screening" / "reports" / "metadata-log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_lines.append("")
    log_lines.append("## Counts")
    for k, v in sorted(status_counts.items()):
        log_lines.append(f"- {k}: {v}")
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    print(f"✓ Records   : {len(records)}")
    for k, v in sorted(status_counts.items()):
        print(f"  {k}: {v}")
    print(f"✓ Wrote     {dedup.relative_to(project.parent)}")
    print(f"✓ Log       {log_path.relative_to(project.parent)}")


if __name__ == "__main__":
    main()
