#!/usr/bin/env python3
"""Fetch open-access PDFs for a list of DOIs, via a cascade of providers.

Provider cascade — each DOI is tried against the list in order; the
first hit that produces a VERIFIED PDF with a publishedVersion (or
acceptedVersion) wins. Lower-quality hits (preprints / unknown
version) are held as a provisional fallback and only committed if
no later provider yields a better version:

  1. Unpaywall          — broad coverage, well-maintained DOI → OA map
  2. OpenAlex           — own `locations[*].pdf_url` (iterates ALL,
                          not just primary); finds repo PDFs Unpaywall
                          misses
  3. Semantic Scholar   — author-uploaded PDFs (includes a lot of what
                          ResearchGate indexes — direct RG fetch is
                          Cloudflare-blocked and ToS-restricted, so we
                          rely on SS's indexed copies)
  4. Europe PMC         — biomedical full-text PDFs (PMCID-keyed)
  5. Publisher direct   — URL templates for known OA publishers
                          (PLOS, eLife, MDPI, Frontiers, JMIR)
  6. arXiv              — preprints (search by DOI cross-ref)
  7. bioRxiv / medRxiv  — preprints (DOI-keyed)
  8. CORE               — institutional repositories (anonymous,
                          best-effort; honors $CORE_API_KEY)

Within a provider, ALL candidate URLs are tried (OpenAlex routinely
returns 3-5 URLs per DOI from different repositories). Candidates
are sorted by version rank — publishedVersion > acceptedVersion >
submittedVersion > unknown — so the best URL inside one provider
is tried first.

Across providers, the cascade stops at the first hit with rank ≥
acceptedVersion. A submittedVersion / unknown hit is kept as a
provisional fallback; the cascade continues looking for a better
version, and only commits the provisional at the end.

After download:
  - Sanity check (size > 1 KB, `%PDF` header).
  - **Title verification** (when pymupdf is installed): extract the
    title from the PDF's first page, compare it via
    `title_similarity` against the expected title from `--with-titles`.
    Reject the download if the similarity drops below 0.5 — closes
    the wrong-paper gap when the DOI returned a landing page or a
    different article.

Save to `raw/<vault>/papers/<first-author-year>.pdf` (slug from
Crossref). Falls back to the legacy flat `raw/papers/` when no
vault is set.

Usage:
    # DOIs as CLI args
    python tools/fetch_oa.py 10.1016/j.neubiorev.2012.10.003 10.xxx/yyy

    # DOIs from a file (regex extraction — works on any text file)
    python tools/fetch_oa.py --from-file candidates.txt

    # Pipe from suggest_readings:
    python tools/suggest_readings.py --forward --top 30 \\
      | python tools/fetch_oa.py --from-stdin

    # Override output directory (default: raw/<vault>/papers/)
    python tools/fetch_oa.py --output-dir raw/snowball/ 10.xxx/yyy

    # Pass expected titles for per-DOI verification (CSV/XLSX with
    # `doi` and `title` columns; e.g. screening/dedup.xlsx)
    python tools/fetch_oa.py --with-titles screening/dedup.xlsx \\
                             --from-stdin

    # Re-try every previously-failed DOI from the last run
    python tools/fetch_oa.py --output-dir out/ --retry-failed

    # Write an enriched missing.md for failed DOIs (corresponding
    # author email + ResearchGate URL + email template)
    python tools/fetch_oa.py --missing-md screening/1st-pass/missing.md \\
                             --from-file dois.txt

    # Set contact email (required by Unpaywall, OpenAlex, CORE ToS)
    UNPAYWALL_EMAIL=you@example.org   # also used for OpenAlex polite pool
    CORE_API_KEY=...                  # optional, raises CORE rate limits
    SEMANTIC_SCHOLAR_API_KEY=...      # optional, lifts SS rate limit from
                                      # 100 req / 5 min to ~10 req/s (free)

The script writes `<output-dir>/fetch_oa_report.json` with per-DOI
status: fetched / paywalled / oa_no_pdf / oa_landing_page_only /
not_available / download_failed / verification_failed /
not_in_unpaywall / invalid_doi / skipped / error. The `attempts`
field per row lists every provider tried with its outcome so a
later `--retry-failed` knows which routes to skip.

Idempotent: existing PDFs are skipped unless `--overwrite`.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, raw_subdir  # noqa: E402
from crossref import (  # noqa: E402
    crossref_metadata,
    crossref_slug as _shared_crossref_slug,
    normalize_doi,
    title_similarity,
)

DEFAULT_DST = raw_subdir("papers")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
DEFAULT_EMAIL = os.getenv("UNPAYWALL_EMAIL", "contact@example.com")
CORE_API_KEY = os.getenv("CORE_API_KEY", "")
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
SLEEP_BETWEEN_DOIS = 0.1
SLEEP_BETWEEN_PROVIDERS = 0.05
DOWNLOAD_TIMEOUT = 60

TITLE_MATCH_THRESHOLD = 0.5   # below → reject (likely wrong paper / landing page)


# Version-rank table — used to prefer publishedVersion over preprints when
# multiple OA versions exist for the same DOI. Values are arbitrary but
# strictly ordered.
VERSION_RANKS = {
    "publishedversion":  3,   # final, peer-reviewed, of-record
    "acceptedversion":   2,   # accepted manuscript (post-peer-review, pre-typeset)
    "submittedversion":  1,   # preprint
}
ACCEPTED_OR_BETTER = 2        # rank ≥ this → done, stop cascading


def version_rank(v):
    """Map a provider-reported version string to its numeric rank.
    Unknown / None returns 0 (treated as preprint-equivalent for sorting)."""
    if not v:
        return 0
    return VERSION_RANKS.get(str(v).strip().lower().replace("-", "").replace("_", ""), 0)


# ----------------------------------------------------------------------
# Helpers

def get_requests():
    try:
        import requests
        return requests
    except ImportError:
        sys.exit("requests not installed. Run: pip install requests")


def slugify(s, max_len=60):
    s = re.sub(r"[^A-Za-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:max_len] or "unknown"


def crossref_slug(doi, requests=None):
    """Return '<first-author-family>-<year>' or None."""
    return _shared_crossref_slug(doi)


def _ua():
    return f"Mozilla/5.0 (graphbib; mailto:{DEFAULT_EMAIL})"


def _safe_get(requests, url, **kwargs):
    """requests.get with our default UA and exception swallowing.
    Returns the Response or None."""
    kwargs.setdefault("timeout", 15)
    headers = kwargs.pop("headers", {}) or {}
    headers.setdefault("User-Agent", _ua())
    try:
        return requests.get(url, headers=headers, **kwargs)
    except Exception:
        return None


# ----------------------------------------------------------------------
# Providers
# Each provider takes (doi, requests) and returns either None (no hit)
# or {"url": "<pdf-url>", "version": "...", "license": "..."}.
# The cascade in fetch_one() iterates over them in PRIORITY order.

def _provider_unpaywall(doi, requests):
    """Returns list[candidate] OR {"_status": "..."} OR None.

    Iterates EVERY oa_location with a PDF URL (today: was first only).
    Each candidate's `version` field comes from Unpaywall's own
    classification so the cascade-level version sort works directly.
    """
    r = _safe_get(
        requests,
        f"https://api.unpaywall.org/v2/{quote(doi, safe='/:')}",
        params={"email": DEFAULT_EMAIL},
    )
    if r is None:
        return None
    if r.status_code == 404:
        return {"_status": "not_in_unpaywall"}
    if r.status_code == 422:
        return {"_status": "invalid_doi"}
    if r.status_code != 200:
        return None
    try:
        j = r.json()
    except Exception:
        return None
    if not j.get("is_oa"):
        return {"_status": "paywalled"}

    locations = []
    best = j.get("best_oa_location") or {}
    if best:
        locations.append(best)
    for loc in (j.get("oa_locations") or []):
        if loc not in locations:
            locations.append(loc)

    candidates = []
    seen_urls = set()
    for loc in locations:
        url = (loc.get("url_for_pdf") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append({
            "url": url,
            "version": loc.get("version"),
            "license": loc.get("license"),
            "host_type": loc.get("host_type"),
        })

    if not candidates:
        return {"_status": "oa_no_pdf"}
    return candidates


def _provider_openalex(doi, requests):
    """Returns list[candidate] — iterates primary_location + every location[*]
    that has a pdf_url. Often 3-5 candidates per DOI vs Unpaywall's 1-2."""
    r = _safe_get(
        requests,
        f"https://api.openalex.org/works/doi:{quote(doi, safe='/:')}",
        params={"mailto": DEFAULT_EMAIL},
    )
    if r is None or r.status_code != 200:
        return None
    try:
        j = r.json()
    except Exception:
        return None
    candidates = []
    seen_urls = set()

    def _add(loc):
        url = (loc.get("pdf_url") or "").strip()
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        candidates.append({
            "url": url,
            "version": loc.get("version"),
            "license": loc.get("license"),
        })

    pl = j.get("primary_location") or {}
    if pl:
        _add(pl)
    for loc in (j.get("locations") or []):
        _add(loc)
    return candidates or None


def _provider_semanticscholar(doi, requests):
    """Semantic Scholar — covers many author-uploaded PDFs that Unpaywall
    and OpenAlex miss (including PDFs hosted on ResearchGate-style
    personal pages that SS has indexed).

    Anonymous tier: 100 req / 5 min. Set $SEMANTIC_SCHOLAR_API_KEY to
    lift the limit (free, sign up at semanticscholar.org/product/api).
    """
    headers = {"User-Agent": _ua()}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
    r = _safe_get(
        requests,
        f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='/')}",
        params={"fields": "openAccessPdf,externalIds"},
        headers=headers,
    )
    if r is None or r.status_code != 200:
        return None
    try:
        j = r.json()
    except Exception:
        return None
    oa = j.get("openAccessPdf") or {}
    url = (oa.get("url") or "").strip()
    if not url:
        return None
    # SS reports `status` as e.g. "BRONZE", "GREEN", "GOLD", "HYBRID" —
    # these are OA-tier labels (Unpaywall-style) not version labels.
    # We can't infer publishedVersion / submittedVersion from that, so
    # we leave version unknown (rank 0). The cascade still tries this
    # candidate; if it brings a publishedVersion, downstream providers
    # can override.
    return [{
        "url": url,
        "version": None,
        "license": oa.get("license"),
        "oa_status": oa.get("status"),
    }]


def _provider_europepmc(doi, requests):
    """Biomedical OA full text via Europe PMC. Keyed by DOI → PMCID.

    PMC mirrors the publishedVersion in nearly every case, so this
    provider's candidate is always tagged publishedVersion."""
    r = _safe_get(
        requests,
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={"query": f"DOI:{doi}", "format": "json", "resultType": "lite"},
    )
    if r is None or r.status_code != 200:
        return None
    try:
        items = (r.json().get("resultList") or {}).get("result") or []
    except Exception:
        return None
    if not items:
        return None
    item = items[0]
    pmcid = (item.get("pmcid") or "").strip()
    if not pmcid:
        return None
    return [{
        "url": f"https://europepmc.org/articles/{pmcid}?pdf=render",
        "version": "publishedVersion",
        "license": item.get("license"),
    }]


def _provider_arxiv(doi, requests):
    """arXiv preprint via the export.arxiv.org API. Search by DOI.
    All arXiv hits are submittedVersion by definition."""
    r = _safe_get(
        requests,
        "https://export.arxiv.org/api/query",
        params={"search_query": f"doi:{doi}", "max_results": 1},
    )
    if r is None or r.status_code != 200:
        return None
    m = re.search(r"<id>http://arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)</id>", r.text or "")
    if not m:
        m = re.search(r"<id>http://arxiv\.org/abs/([a-z\-]+/[0-9]+(?:v\d+)?)</id>", r.text or "")
    if not m:
        return None
    arxiv_id = m.group(1)
    return [{
        "url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        "version": "submittedVersion",
        "license": "arxiv-perpetual",
    }]


def _provider_biorxiv(doi, requests):
    """bioRxiv / medRxiv preprint server. Always submittedVersion."""
    candidates = []
    for server in ("biorxiv", "medrxiv"):
        r = _safe_get(requests, f"https://api.biorxiv.org/details/{server}/{doi}",
                      timeout=10)
        if r is None or r.status_code != 200:
            continue
        try:
            collection = r.json().get("collection") or []
        except Exception:
            continue
        if not collection:
            continue
        latest_doi = (collection[-1].get("doi") or doi).strip()
        candidates.append({
            "url": f"https://www.{server}.org/content/{latest_doi}.full.pdf",
            "version": "submittedVersion",
            "license": (collection[-1].get("license") or ""),
        })
    return candidates or None


def _provider_core(doi, requests):
    """CORE.ac.uk — institutional-repo aggregator. Iterates up to 3 results
    per DOI; their downloadUrl can be authorVersion, publishedVersion, or
    submittedVersion — CORE doesn't classify so version stays unknown."""
    headers = {"User-Agent": _ua()}
    if CORE_API_KEY:
        headers["Authorization"] = f"Bearer {CORE_API_KEY}"
    r = _safe_get(
        requests,
        "https://api.core.ac.uk/v3/search/works",
        params={"q": f'doi:"{doi}"', "limit": 3},
        headers=headers,
    )
    if r is None or r.status_code != 200:
        return None
    try:
        results = r.json().get("results") or []
    except Exception:
        return None
    candidates = []
    seen = set()
    for item in results:
        url = (item.get("downloadUrl") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        candidates.append({
            "url": url,
            "version": item.get("documentType"),
            "license": "",
        })
    return candidates or None


# Publisher prefix → PDF URL builder. Each builder receives the DOI
# and returns the URL string (or None on no match).
def _publisher_plos(doi):
    # 10.1371/journal.pone.0123456 → https://journals.plos.org/plosone/article/file?id=10.1371/...&type=printable
    m = re.match(r"^10\.1371/journal\.([a-z]+)\.\d+$", doi)
    if not m:
        return None
    journal_slug = {
        "pone": "plosone", "pbio": "plosbiology", "pmed": "plosmedicine",
        "pntd": "plosntds", "ppat": "plospathogens", "pgen": "plosgenetics",
        "pcbi": "ploscompbiol", "pone-d": "plosone",  # fallback
    }.get(m.group(1).split("-")[0], "plosone")
    return f"https://journals.plos.org/{journal_slug}/article/file?id={doi}&type=printable"


def _publisher_elife(doi):
    # 10.7554/eLife.12345 → https://elifesciences.org/articles/12345/exec.pdf
    m = re.match(r"^10\.7554/eLife\.(\d+)$", doi, re.I)
    if not m:
        return None
    return f"https://cdn.elifesciences.org/articles/{m.group(1)}/elife-{m.group(1)}.pdf"


def _publisher_mdpi(doi):
    # 10.3390/<journal-slug><id> — MDPI exposes /article/<doi>/pdf
    if not doi.startswith("10.3390/"):
        return None
    return f"https://www.mdpi.com/article/{doi}/pdf"


def _publisher_frontiers(doi):
    # 10.3389/<journal>.<year>.<id> → https://www.frontiersin.org/articles/10.3389/.../pdf
    if not doi.startswith("10.3389/"):
        return None
    return f"https://www.frontiersin.org/articles/{doi}/pdf"


def _publisher_jmir(doi):
    if not doi.startswith("10.2196/"):
        return None
    return f"https://www.jmir.org/api/download?filename={doi.split('/')[1]}.pdf&alt_name={doi.split('/')[1]}"


PUBLISHER_BUILDERS = [
    ("plos", _publisher_plos),
    ("elife", _publisher_elife),
    ("mdpi", _publisher_mdpi),
    ("frontiers", _publisher_frontiers),
    ("jmir", _publisher_jmir),
]


def _provider_publisher(doi, requests):
    """Construct a direct PDF URL for known OA publishers (no API call).
    Always publishedVersion."""
    for name, builder in PUBLISHER_BUILDERS:
        url = builder(doi)
        if url:
            return [{
                "url": url, "version": "publishedVersion", "license": "",
                "publisher_imprint": name,
            }]
    return None


# Cascade order: publisher-direct and publishedVersion-likely providers
# first, so the version-rank sort doesn't need to backtrack. Within each
# provider, candidates are sorted by version rank too.
PROVIDERS = [
    ("unpaywall",       _provider_unpaywall),
    ("openalex",        _provider_openalex),
    ("semanticscholar", _provider_semanticscholar),
    ("europepmc",       _provider_europepmc),
    ("publisher",       _provider_publisher),
    ("arxiv",           _provider_arxiv),
    ("biorxiv",         _provider_biorxiv),
    ("core",            _provider_core),
]


# ----------------------------------------------------------------------
# Download + PDF verification

def download_pdf(url, target_path, requests, overwrite=False):
    if target_path.exists() and not overwrite:
        return False, "exists"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(
            url,
            stream=True,
            timeout=DOWNLOAD_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": _ua()},
        )
        r.raise_for_status()
    except Exception as e:
        return False, f"http_error: {type(e).__name__}: {e}"

    ct = (r.headers.get("Content-Type") or "").lower()
    is_pdf = ("pdf" in ct) or url.lower().split("?")[0].endswith(".pdf")
    if not is_pdf:
        return False, f"non_pdf_content_type: {ct or 'unknown'}"

    tmp = target_path.with_suffix(target_path.suffix + ".part")
    try:
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        if tmp.stat().st_size < 1024:
            tmp.unlink(missing_ok=True)
            return False, "downloaded_file_too_small"
        with tmp.open("rb") as f:
            head = f.read(8)
        if not head.startswith(b"%PDF"):
            tmp.unlink(missing_ok=True)
            return False, "not_a_pdf_header"
        tmp.replace(target_path)
        return True, None
    except Exception as e:
        tmp.unlink(missing_ok=True)
        return False, f"write_error: {type(e).__name__}: {e}"


def extract_pdf_title(path):
    """Best-effort title extraction from a downloaded PDF.

    Returns the extracted title string or None when we can't extract
    (no pymupdf, broken PDF, no title candidate). When None, the
    caller MUST NOT reject — verification is optional, not blocking.
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        return None
    try:
        doc = fitz.open(path)
    except Exception:
        return None
    try:
        meta_title = (doc.metadata.get("title") or "").strip() if doc.metadata else ""
        # Metadata title is often junk: "Microsoft Word - paper.docx",
        # one-line filenames, etc. Heuristic: trust it only when it's
        # > 15 chars and not a filename.
        if (15 < len(meta_title) < 250
                and not meta_title.lower().endswith((".docx", ".doc", ".pdf"))
                and not re.match(r"^(untitled|microsoft|adobe|word).*", meta_title.lower())):
            return meta_title
        # Fallback: longest plausible line in first page text
        if doc.page_count == 0:
            return None
        text = doc[0].get_text() or ""
        lines = [ln.strip() for ln in text.split("\n")[:40] if ln.strip()]
        if not lines:
            return None
        candidates = [
            ln for ln in lines[:20]
            if 20 < len(ln) < 250 and re.search(r"[A-Za-z]{4,}", ln)
            and not re.match(r"^(abstract|introduction|methods?|results?|"
                             r"discussion|background|keywords?|page \d+|"
                             r"doi|http|received|accepted|published|"
                             r"\d{4}\s*[—,-])", ln, re.I)
        ]
        if not candidates:
            return None
        return max(candidates, key=len)
    finally:
        try:
            doc.close()
        except Exception:
            pass


def verify_pdf_title(path, expected_title, threshold=TITLE_MATCH_THRESHOLD):
    """Compare a PDF's extracted title to the expected one.

    Returns (ok, sim_or_None, extracted_or_None):
      - ok=True  : accept the PDF (sim ≥ threshold, OR no expected title given,
                   OR pymupdf not available — verification skipped)
      - ok=False : reject; the PDF is for a different paper / a landing page
    """
    if not expected_title:
        return True, None, None
    extracted = extract_pdf_title(path)
    if not extracted:
        return True, None, None
    sim = title_similarity(expected_title, extracted)
    return sim >= threshold, sim, extracted


# ----------------------------------------------------------------------
# fetch_one — cascading provider loop

# Per-provider hard statuses (no point retrying within this DOI):
_STATUS_HARD_STOPS = {"invalid_doi"}


def _normalize_provider_return(value):
    """Normalize a provider's return value to (list_of_candidates, meta_status).

    Providers can return:
      - None                      → ([], None)
      - {"_status": "..."}        → ([], "<status>")
      - {url, version, …}         → ([single_candidate], None)
      - [c1, c2, …]               → (sorted_by_version_desc, None)
    """
    if value is None:
        return [], None
    if isinstance(value, dict):
        if "_status" in value:
            return [], value["_status"]
        return [value], None
    if isinstance(value, list):
        # Sort candidates within a provider: publishedVersion → accepted → submitted → unknown
        return sorted(value, key=lambda c: -version_rank(c.get("version"))), None
    return [], None


def fetch_one(doi, dst, requests, expected_title=None, overwrite=False,
              skip_providers=None):
    """Walk PROVIDERS, prefer publishedVersion, accept all URLs within
    a provider before moving on.

    Strategy:
      1. For each provider, get its candidates (list of {url, version}).
      2. Within a provider, try candidates in descending version-rank
         order — published > accepted > submitted > unknown.
      3. On first verified download:
          - rank ≥ ACCEPTED_OR_BETTER (acceptedVersion or
            publishedVersion) → DONE, return immediately.
          - rank < ACCEPTED_OR_BETTER (submittedVersion / unknown) →
            keep as a `provisional` fallback, CONTINUE the cascade
            in case a later provider has a publishedVersion.
      4. At end of cascade, commit the best fallback. If nothing was
         downloaded, return not_available.

    `skip_providers` (set) lets --retry-failed avoid providers whose
    previous URLs already returned bad downloads.
    """
    skip = set(skip_providers or [])
    slug = crossref_slug(doi) or slugify(doi.replace("/", "-"))
    target = dst / f"{slug}.pdf"

    if target.exists() and not overwrite:
        return {
            "doi": doi,
            "status": "skipped",
            "path": str(target.relative_to(REPO_ROOT)),
            "attempts": [],
        }

    attempts = []
    seen_meta_status = None  # e.g. paywalled, oa_no_pdf, invalid_doi
    # provisional: (result_dict_partial, rank, tmp_path_on_disk)
    provisional = None

    def _finalize(result_dict, tmp_path):
        """Promote a temp file to the canonical target path."""
        if tmp_path != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.replace(target)
        try:
            result_dict["path"] = str(target.relative_to(REPO_ROOT))
        except ValueError:
            # target not under REPO_ROOT (e.g. caller chose a path
            # outside the repo, or tests use a tmp dir). Use absolute.
            result_dict["path"] = str(target)
        result_dict["attempts"] = attempts
        return result_dict

    for prov_idx, (name, fn) in enumerate(PROVIDERS):
        if name in skip:
            attempts.append({"source": name, "found": False, "skipped": True})
            continue
        try:
            raw = fn(doi, requests)
        except Exception as e:
            attempts.append({"source": name, "found": False,
                             "error": f"{type(e).__name__}: {e}"})
            time.sleep(SLEEP_BETWEEN_PROVIDERS)
            continue
        time.sleep(SLEEP_BETWEEN_PROVIDERS)

        candidates, meta_status = _normalize_provider_return(raw)
        if meta_status:
            attempts.append({"source": name, "found": False,
                             "meta_status": meta_status})
            seen_meta_status = seen_meta_status or meta_status
            if meta_status in _STATUS_HARD_STOPS:
                break
            continue
        if not candidates:
            attempts.append({"source": name, "found": False})
            continue

        for cand_idx, cand in enumerate(candidates):
            url = (cand.get("url") or "").strip()
            if not url:
                continue
            # Each URL gets its own temp path so we don't clobber the
            # provisional in case of a verification failure mid-cascade.
            tmp = target.with_suffix(f".pdf.attempt.{name}.{cand_idx}")

            ok, reason = download_pdf(url, tmp, requests, overwrite=True)
            if not ok:
                attempts.append({
                    "source": name, "found": True, "url": url,
                    "version": cand.get("version"),
                    "download_status": reason,
                })
                continue

            v_ok, sim, extracted = verify_pdf_title(tmp, expected_title)
            if not v_ok:
                tmp.unlink(missing_ok=True)
                attempts.append({
                    "source": name, "found": True, "url": url,
                    "version": cand.get("version"),
                    "download_status": "ok",
                    "verification": "rejected",
                    "title_sim": sim,
                    "title_extracted": (extracted or "")[:80],
                })
                continue

            rank = version_rank(cand.get("version"))
            attempts.append({
                "source": name, "found": True, "url": url,
                "version": cand.get("version"),
                "download_status": "ok",
                "verification": "accepted" if sim is not None else "skipped",
                "title_sim": sim,
            })

            partial = {
                "doi": doi,
                "status": "fetched",
                "source": name,
                "license": cand.get("license"),
                "version": cand.get("version"),
                "title_sim": sim,
            }

            if rank >= ACCEPTED_OR_BETTER:
                # publishedVersion or acceptedVersion → done.
                # Clean up any provisional we held back.
                if provisional and provisional[2].exists():
                    provisional[2].unlink(missing_ok=True)
                return _finalize(partial, tmp)

            # submittedVersion / unknown → keep as provisional,
            # continue the cascade in case a later provider has a
            # publishedVersion.
            if provisional is None or rank > provisional[1]:
                if provisional and provisional[2].exists():
                    provisional[2].unlink(missing_ok=True)
                provisional = (partial, rank, tmp)
            else:
                tmp.unlink(missing_ok=True)
            # Within this provider, no need to keep iterating since we
            # already have its best candidate as provisional.
            break

    # End of cascade — commit the provisional if we got one.
    if provisional:
        partial, rank, tmp = provisional
        partial["note"] = ("no publishedVersion found in cascade — "
                           f"keeping {partial.get('version') or 'unknown-version'} "
                           f"from {partial.get('source')}")
        return _finalize(partial, tmp)

    # Nothing downloaded
    if seen_meta_status in ("paywalled", "oa_no_pdf", "not_in_unpaywall", "invalid_doi"):
        status = seen_meta_status
    else:
        status = "not_available"
    return {"doi": doi, "status": status, "attempts": attempts}


# ----------------------------------------------------------------------
# Inputs: DOIs and expected titles

def collect_dois(args):
    """Resolve DOIs from args / file / stdin."""
    raw = []
    raw.extend(args.dois)
    if args.from_file:
        text = Path(args.from_file).read_text(encoding="utf-8")
        raw.extend(DOI_RE.findall(text))
    if args.from_stdin:
        text = sys.stdin.read()
        raw.extend(DOI_RE.findall(text))

    seen = set()
    out = []
    for d in raw:
        d = d.strip().rstrip(".,;)").lower()
        if not d or d in seen:
            continue
        seen.add(d)
        if not DOI_RE.fullmatch(d):
            m = DOI_RE.search(d)
            if not m:
                continue
            d = m.group(0).rstrip(".,;)").lower()
            if d in seen:
                continue
            seen.add(d)
        out.append(d)
    return out


def load_expected_titles(path):
    """Load {doi: title} from a CSV / XLSX / dict-like JSON file.

    The file must have at least `doi` and `title` columns. Other
    columns are ignored. Used by `--with-titles` to drive the
    post-download verification step.
    """
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        sys.exit(f"--with-titles: {p} not found.")
    from tabular import read_records
    _, records = read_records(p)
    out = {}
    for r in records:
        doi = normalize_doi(r.get("doi") or "")
        title = (r.get("title") or "").strip()
        if doi and title:
            out[doi] = title
    return out


def load_previous_failures(report_path):
    """Read fetch_oa_report.json, return list of (doi, providers_already_tried)
    for rows that didn't succeed (status not in {fetched, skipped})."""
    if not report_path.exists():
        return []
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for row in (data.get("results") or []):
        if row.get("status") in ("fetched", "skipped"):
            continue
        doi = (row.get("doi") or "").strip().lower()
        if not doi:
            continue
        # Build a set of providers that returned "found=True but
        # download/verify failed" — those we'll skip on retry to
        # avoid re-hitting a known-bad URL. Providers that returned
        # found=False are retried (they may have new data now).
        skip = {
            a.get("source") for a in (row.get("attempts") or [])
            if a.get("source") and a.get("download_status") not in (None, "ok", "exists")
        }
        out.append((doi, skip))
    return out


# ----------------------------------------------------------------------
# Enriched missing.md

def _researchgate_url(title):
    """Construct a ResearchGate search URL from the title."""
    if not title:
        return ""
    return ("https://www.researchgate.net/search/publication?q="
            + quote(title[:200], safe=""))


def _author_email_from_crossref(doi):
    """Best-effort email lookup. Crossref rarely exposes emails; this
    falls back to ORCID and corresponding-author markers."""
    md = crossref_metadata(doi) or {}
    # crossref_metadata only returns title/first_author/year/journal.
    # For emails we'd need a deeper Crossref call; defer for now and
    # surface what we have.
    return {
        "first_author": md.get("first_author", ""),
        "year": md.get("year", ""),
        "journal": md.get("journal", ""),
    }


def _email_template(title, first_author, journal, year):
    return (
        f"Subject: Reprint request — {title[:80]}\n\n"
        f"Dear Dr. {first_author or '[corresponding author]'},\n\n"
        f"I am preparing a systematic review and would like to include your "
        f"work \"{title}\" ({journal}, {year}) in the analysis.\n\n"
        f"Would you be willing to share a PDF of the full text? I could not "
        f"locate an open-access copy.\n\n"
        f"Thank you very much for your time,\n"
        f"[Your name]"
    )


def write_missing_md(failed_rows, expected_titles, out_path):
    """Write an enriched missing.md with retrieval hints per row."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Articles not retrieved by fetch_oa cascade",
        "",
        f"> {len(failed_rows)} DOIs the open-access cascade could not "
        f"deliver. For each row: the providers we tried, a ResearchGate "
        f"search link (often surfaces author-uploaded copies), and a "
        f"ready-to-send reprint-request email template.",
        "",
    ]
    for row in failed_rows:
        doi = row.get("doi", "?")
        title = expected_titles.get(normalize_doi(doi), "") or "[title unknown]"
        meta = _author_email_from_crossref(doi)
        rg_url = _researchgate_url(title)

        lines.append(f"## `{doi}`")
        lines.append("")
        lines.append(f"- **Title**     : {title}")
        if meta.get("first_author"):
            lines.append(f"- **First author**: {meta['first_author']} ({meta.get('year', '?')})")
        if meta.get("journal"):
            lines.append(f"- **Journal**   : {meta['journal']}")
        lines.append(f"- **Status**    : `{row.get('status')}`")
        tried = ", ".join(
            f"{a.get('source')}({'ok' if a.get('found') else 'no-hit'})"
            for a in (row.get("attempts") or [])
        )
        lines.append(f"- **Providers tried**: {tried or '—'}")
        lines.append(f"- **ResearchGate search**: <{rg_url}>")
        lines.append("")
        lines.append("<details><summary>Reprint-request email</summary>")
        lines.append("")
        lines.append("```")
        lines.append(_email_template(
            title,
            meta.get("first_author", ""),
            meta.get("journal", ""),
            meta.get("year", ""),
        ))
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------
# CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("dois", nargs="*", help="DOIs to fetch (one or more).")
    ap.add_argument("--from-file", help="Read DOIs from a text file (regex extraction).")
    ap.add_argument("--from-stdin", action="store_true",
                    help="Read DOIs from stdin (regex extraction).")
    ap.add_argument("--output-dir", default=str(DEFAULT_DST),
                    help=f"Where to save PDFs (default: {DEFAULT_DST}).")
    ap.add_argument("--overwrite", action="store_true",
                    help="Overwrite existing PDFs.")
    ap.add_argument("--with-titles", default=None,
                    help="CSV/XLSX with `doi` + `title` columns — enables "
                         "post-download title verification (rejects "
                         "wrong-paper PDFs / landing pages).")
    ap.add_argument("--retry-failed", action="store_true",
                    help="Read <output-dir>/fetch_oa_report.json and re-try "
                         "every DOI that didn't succeed. Skips providers "
                         "that already failed on those DOIs.")
    ap.add_argument("--missing-md", default=None,
                    help="Write an enriched missing.md for unsuccessful DOIs "
                         "(corresponding author hints, ResearchGate URL, "
                         "email template).")
    args = ap.parse_args()

    requests = get_requests()

    dst = Path(args.output_dir).expanduser().resolve()
    dst.mkdir(parents=True, exist_ok=True)
    report_path = dst / "fetch_oa_report.json"

    expected_titles = load_expected_titles(args.with_titles) if args.with_titles else {}
    skip_map = {}   # doi → set(providers) to skip

    if args.retry_failed:
        previous = load_previous_failures(report_path)
        if not previous:
            sys.exit(f"--retry-failed: no failures found in {report_path}.")
        dois = [d for d, _ in previous]
        skip_map = dict(previous)
        print(f"  · --retry-failed: {len(dois)} DOIs from {report_path.name}",
              file=sys.stderr)
    else:
        dois = collect_dois(args)
    if not dois:
        sys.exit("No DOIs provided. Pass them as args, --from-file, "
                 "--from-stdin, or use --retry-failed.")

    if DEFAULT_EMAIL == "contact@example.com":
        print("  ! UNPAYWALL_EMAIL env var not set — using placeholder. "
              "Unpaywall + OpenAlex + CORE ask for a valid contact email; "
              "set yours via `export UNPAYWALL_EMAIL=you@example.org`.",
              file=sys.stderr)

    # Warn when pymupdf is unavailable (title verification will be skipped)
    if expected_titles:
        try:
            import fitz  # noqa: F401
        except ImportError:
            print("  ! pymupdf (fitz) not installed — title verification "
                  "will be SKIPPED for downloaded PDFs. "
                  "Run `pip install pymupdf` to enable wrong-paper detection.",
                  file=sys.stderr)

    print(f"  · {len(dois)} DOIs to process → "
          f"{dst.relative_to(REPO_ROOT) if str(dst).startswith(str(REPO_ROOT)) else dst}",
          file=sys.stderr)
    print(f"  · Providers in cascade: "
          f"{', '.join(p[0] for p in PROVIDERS)}",
          file=sys.stderr)
    if expected_titles:
        print(f"  · Title verification enabled "
              f"({len(expected_titles)} expected titles loaded).",
              file=sys.stderr)

    report = []
    counts = {}
    for i, doi in enumerate(dois, 1):
        expected = expected_titles.get(normalize_doi(doi))
        result = fetch_one(
            doi, dst, requests,
            expected_title=expected,
            overwrite=args.overwrite,
            skip_providers=skip_map.get(doi, set()),
        )
        report.append(result)
        counts[result["status"]] = counts.get(result["status"], 0) + 1

        tag = {
            "fetched": "✓", "skipped": "·",
            "paywalled": "$", "oa_no_pdf": "?", "oa_landing_page_only": "?",
            "not_in_unpaywall": "?", "not_available": "?",
            "invalid_doi": "✗", "download_failed": "✗", "error": "✗",
        }.get(result["status"], "·")
        suffix = ""
        if result["status"] == "fetched":
            via = result.get("source", "?")
            sim = result.get("title_sim")
            sim_str = f" sim={sim:.2f}" if sim is not None else ""
            suffix = f" → {result['path']} (via {via}{sim_str})"
        elif result["status"] == "not_available":
            tried = sum(1 for a in result.get("attempts", []) if a.get("found"))
            suffix = f"  (no PDF after {len(result.get('attempts', []))} providers, "
            suffix += f"{tried} returned a URL)"
        print(f"  {tag} [{i}/{len(dois)}] {doi}{suffix}", file=sys.stderr)
        time.sleep(SLEEP_BETWEEN_DOIS)

    report_path.write_text(
        json.dumps({"summary": counts, "results": report},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if args.missing_md:
        failed = [r for r in report if r.get("status") not in ("fetched", "skipped")]
        missing_path = Path(args.missing_md).expanduser().resolve()
        write_missing_md(failed, expected_titles, missing_path)
        print(f"\nMissing: {missing_path.relative_to(REPO_ROOT) if str(missing_path).startswith(str(REPO_ROOT)) else missing_path}",
              file=sys.stderr)

    print(f"\n=== {len(dois)} processed ===", file=sys.stderr)
    for status, n in sorted(counts.items(), key=lambda t: -t[1]):
        print(f"  {status}: {n}", file=sys.stderr)
    # Provider-level success breakdown (only for `fetched` rows)
    by_source = {}
    for r in report:
        if r.get("status") == "fetched":
            by_source[r.get("source", "?")] = by_source.get(r.get("source", "?"), 0) + 1
    if by_source:
        print(f"\n  Successes by provider:", file=sys.stderr)
        for src, n in sorted(by_source.items(), key=lambda t: -t[1]):
            print(f"    {src}: {n}", file=sys.stderr)
    print(f"\nReport: {report_path.relative_to(REPO_ROOT) if str(report_path).startswith(str(REPO_ROOT)) else report_path}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
