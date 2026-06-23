#!/usr/bin/env python3
"""Shared Crossref helpers - used by both the wiki side (parse_references,
fetch_oa) and the extractor side (screen_fetch_metadata, the upcoming
/extractor-screen-validate command).

All helpers share a single on-disk cache at
`tools/.cache/crossref.json` so that re-runs across tools are free.
The cache is keyed by operation:

    {
      "validate:<doi>":   true|false,
      "search:<query-hash>": "10.xxx/yyy" | null,
      "metadata:<doi>":   {"title": ..., "first_author": ..., "year": ...},
      "slug:<doi>":       "<family>-<year>",
    }

Definitive answers (200 / 404) are cached; transient errors (5xx,
timeouts) are NOT cached - we stay optimistic on the next call so a
flaky network doesn't poison the cache.

Public API:
    normalize_doi(raw)                  → cleaned DOI or ""
    norm_title(s)                       → lowercased, accent-stripped, collapsed
    title_overlap(a, b)                 → token-Jaccard [0..1]
    title_similarity(a, b)              → SequenceMatcher ratio [0..1]
    crossref_validate(doi, cache=None)  → True if DOI exists at Crossref
    crossref_metadata(doi, cache=None)  → {"title","first_author","year","journal"}
    crossref_search(query, cache=None)  → DOI string or None
    crossref_slug(doi, cache=None)      → "<family>-<year>" or None
    load_cache() / save_cache(cache)    → persistent JSON
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).parent.parent
CACHE_DIR = REPO_ROOT / "tools" / ".cache"
CACHE_FILE = CACHE_DIR / "crossref.json"

EMAIL = (
    os.environ.get("CROSSREF_EMAIL")
    or os.environ.get("UNPAYWALL_EMAIL")
    or "graphbib@local"
)
USER_AGENT = f"GraphBib/0.1 (mailto:{EMAIL})"
SLEEP_BETWEEN = 0.05   # ~20 req/s, polite for Crossref
TIMEOUT = 12

# Thresholds (tunable; matches what parse_references.py used before)
MIN_SEARCH_SCORE = 50.0       # Crossref relevance score gate
MIN_TITLE_OVERLAP = 0.5       # token-Jaccard gate for crossref_search
MIN_TITLE_MATCH = 0.75        # SequenceMatcher ratio gate for verify flow
DOI_URL_RE = re.compile(r"^https?://(dx\.)?doi\.org/", re.I)


# ----------------------------------------------------------------------
# Normalizers (pure, no I/O)

def normalize_doi(raw):
    """Strip URL prefix, trim, lowercase. Return '' if not a valid 10.xxx DOI."""
    if not raw:
        return ""
    s = str(raw).strip()
    s = DOI_URL_RE.sub("", s)
    s = s.strip(" .;,")
    return s.lower() if s.startswith("10.") else ""


def norm_title(s):
    """Lowercase, strip accents, collapse non-alnum to single space."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def title_overlap(a, b):
    """Token-Jaccard on words of length ≥ 4 - used by crossref_search gate."""
    ta = set(re.findall(r"\w{4,}", (a or "").lower()))
    tb = set(re.findall(r"\w{4,}", (b or "").lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def title_similarity(a, b):
    """SequenceMatcher ratio on normalized titles. 0..1 - used for verify."""
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def slugify(s, max_len=60):
    """Filesystem-safe slug component - kebab-case, ASCII-only."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.lower()).strip("-")
    return s[:max_len]


# ----------------------------------------------------------------------
# Cache

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ----------------------------------------------------------------------
# Crossref API calls

def _requests():
    """Lazy import - keeps cold-import time low for callers that don't hit the net."""
    import requests
    return requests


def _query_hash(q):
    return hashlib.sha1(q.strip().lower().encode("utf-8")).hexdigest()[:16]


def crossref_validate(doi, cache=None):
    """Return True if Crossref recognizes the DOI.

    Uses /works/{doi}/agency (lightweight, ~5 KB). Caches definitive
    results (200/404). On transient failure returns True (optimistic - 
    don't drop legitimate DOIs because of a flaky network).
    """
    doi = normalize_doi(doi)
    if not doi:
        return False
    cache = load_cache() if cache is None else cache
    key = f"validate:{doi}"
    if key in cache:
        return cache[key]

    requests = _requests()
    for _ in range(2):
        try:
            r = requests.get(
                f"https://api.crossref.org/works/{quote(doi, safe='/:')}/agency",
                timeout=TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            time.sleep(SLEEP_BETWEEN)
            if r.status_code == 200:
                cache[key] = True
                return True
            if r.status_code == 404:
                cache[key] = False
                return False
            time.sleep(0.5)
        except Exception:
            time.sleep(0.5)
    return True  # optimistic on transient failure (not cached)


def crossref_metadata(doi, cache=None):
    """Return canonical title/first_author/year/journal from Crossref, or None.

    Cached. Used to cross-check a DOI against the user-supplied row
    (title / year mismatch detection).
    """
    doi = normalize_doi(doi)
    if not doi:
        return None
    cache = load_cache() if cache is None else cache
    key = f"metadata:{doi}"
    if key in cache:
        return cache[key] or None

    requests = _requests()
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{quote(doi, safe='/:')}",
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            params={"mailto": EMAIL},
        )
        time.sleep(SLEEP_BETWEEN)
    except Exception:
        return None
    if r.status_code == 404:
        cache[key] = None
        return None
    if r.status_code != 200:
        return None  # transient - don't cache

    try:
        m = r.json().get("message", {})
    except Exception:
        return None

    title = (m.get("title") or [""])[0]
    authors = m.get("author") or []
    first_author = ""
    if authors:
        a = authors[0]
        first_author = a.get("family") or a.get("name") or ""
    # Year: prefer issued, fall back to published-print / published-online
    year = ""
    for k in ("issued", "published-print", "published-online", "created"):
        block = m.get(k) or {}
        parts = (block.get("date-parts") or [[]])[0]
        if parts:
            year = str(parts[0])
            break
    journal = (m.get("container-title") or [""])[0]

    out = {
        "title": title.strip(),
        "first_author": first_author.strip(),
        "year": year,
        "journal": journal.strip(),
    }
    cache[key] = out
    return out


def crossref_search(query, cache=None):
    """Free-text bibliographic search. Returns DOI string or None.

    Gate: Crossref relevance score ≥ MIN_SEARCH_SCORE AND token-Jaccard
    title overlap between the query and the best hit ≥ MIN_TITLE_OVERLAP.
    Cached by query SHA1 (negative results cached as null).
    """
    if not query or len(query.strip()) < 8:
        return None
    cache = load_cache() if cache is None else cache
    qhash = _query_hash(query)
    key = f"search:{qhash}"
    if key in cache:
        return cache[key] or None

    requests = _requests()
    try:
        r = requests.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": query[:500], "rows": 3, "mailto": EMAIL},
            timeout=TIMEOUT + 3,
            headers={"User-Agent": USER_AGENT},
        )
        time.sleep(SLEEP_BETWEEN)
        r.raise_for_status()
        items = r.json()["message"].get("items") or []
    except Exception:
        return None

    if not items:
        cache[key] = None
        return None
    best = items[0]
    score = best.get("score") or 0.0
    if score < MIN_SEARCH_SCORE:
        cache[key] = None
        return None
    title = (best.get("title") or [""])[0]
    if title_overlap(query, title) < MIN_TITLE_OVERLAP:
        cache[key] = None
        return None
    doi = normalize_doi(best.get("DOI") or "")
    cache[key] = doi or None
    return doi or None


def crossref_slug(doi, cache=None):
    """Return '<first-author-family>-<year>' or None on failure.

    Used by fetch_oa.py to name PDFs and by the slug-rehab pass in
    screen_fetch_metadata.py to fix `anon-<year>` rows once a DOI is
    recovered.
    """
    md = crossref_metadata(doi, cache=cache)
    if not md:
        return None
    family = md.get("first_author") or ""
    year = md.get("year") or ""
    if not family or not year:
        return None
    return f"{slugify(family)}-{year}"


# ----------------------------------------------------------------------
# Smoke test (only when run as a script)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--validate", metavar="DOI", help="Crossref validate this DOI")
    ap.add_argument("--metadata", metavar="DOI", help="Crossref metadata for this DOI")
    ap.add_argument("--search", metavar="QUERY", help="Crossref bibliographic search")
    ap.add_argument("--slug", metavar="DOI", help="Derive '<family>-<year>' slug from DOI")
    args = ap.parse_args()

    cache = load_cache()
    if args.validate:
        print(crossref_validate(args.validate, cache=cache))
    if args.metadata:
        print(json.dumps(crossref_metadata(args.metadata, cache=cache), indent=2, ensure_ascii=False))
    if args.search:
        print(crossref_search(args.search, cache=cache))
    if args.slug:
        print(crossref_slug(args.slug, cache=cache))
    save_cache(cache)
