#!/usr/bin/env python3
"""Fetch open-access PDFs for a list of DOIs.

Workflow:
  - Query Unpaywall (free, no key, just an email) for each DOI.
  - If `is_oa` and a PDF URL is available, download it.
  - Save to `raw/papers/<first-author-year>.pdf` (slug from Crossref).
  - Skip DOIs that are paywalled, already downloaded, or fail.

Usage:
    # DOIs as CLI args
    python tools/fetch_oa.py 10.1016/j.neubiorev.2012.10.003 10.xxx/yyy

    # DOIs from a file (one per line, or any text file — DOI regex is run)
    python tools/fetch_oa.py --from-file candidates.txt

    # Pipe from suggest_readings:
    python tools/suggest_readings.py --forward --top 30 \\
      | python tools/fetch_oa.py --from-stdin

    # Override output directory (default: raw/papers/)
    python tools/fetch_oa.py --output-dir raw/snowball/ 10.xxx/yyy

    # Set your contact email (required by Unpaywall ToS)
    UNPAYWALL_EMAIL=you@example.org python tools/fetch_oa.py 10.xxx/yyy

The script writes `<output-dir>/fetch_oa_report.json` summarizing each
DOI's status: fetched / paywalled / not_in_unpaywall / oa_no_pdf /
download_failed / skipped / error.

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

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DST = REPO_ROOT / "raw" / "papers"

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
DEFAULT_EMAIL = os.getenv("UNPAYWALL_EMAIL", "contact@example.com")
SLEEP_BETWEEN = 0.1   # ~10 req/s, polite for both Unpaywall and Crossref
DOWNLOAD_TIMEOUT = 60


def get_requests():
    try:
        import requests
        return requests
    except ImportError:
        sys.exit("requests not installed. Run: pip install requests")


def slugify(s, max_len=60):
    s = re.sub(r"[^A-Za-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:max_len] or "unknown"


def crossref_slug(doi, requests):
    """Return '<first-author-family>-<year>' or None on failure."""
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{quote(doi, safe='/:')}",
            headers={"User-Agent": f"graphbib/0.1 (mailto:{DEFAULT_EMAIL})"},
            timeout=10,
        )
        r.raise_for_status()
        msg = r.json()["message"]
        first_author = (msg.get("author") or [{}])[0]
        family = first_author.get("family") or first_author.get("name") or "unknown"
        year = "0000"
        if msg.get("issued", {}).get("date-parts"):
            year = str(msg["issued"]["date-parts"][0][0])
        return f"{slugify(family)}-{year}"
    except Exception:
        return None


def unpaywall_lookup(doi, requests):
    try:
        r = requests.get(
            f"https://api.unpaywall.org/v2/{quote(doi, safe='/:')}",
            params={"email": DEFAULT_EMAIL},
            timeout=15,
        )
        if r.status_code == 404:
            return {"_status": "not_in_unpaywall"}
        if r.status_code == 422:
            return {"_status": "invalid_doi"}
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_status": "error", "_error": f"{type(e).__name__}: {e}"}


def best_oa_location(unpaywall_data):
    """Pick the best OA location with a PDF URL, prefer publisher / repository."""
    if not unpaywall_data.get("is_oa"):
        return None
    candidates = []
    best = unpaywall_data.get("best_oa_location") or {}
    if best:
        candidates.append(best)
    for loc in unpaywall_data.get("oa_locations") or []:
        if loc not in candidates:
            candidates.append(loc)
    for loc in candidates:
        if loc.get("url_for_pdf"):
            return {
                "url": loc["url_for_pdf"],
                "host_type": loc.get("host_type"),
                "license": loc.get("license"),
                "version": loc.get("version"),
            }
    # Fallback: HTML landing page (not a PDF, but at least an URL)
    for loc in candidates:
        if loc.get("url"):
            return {
                "url": loc["url"],
                "host_type": loc.get("host_type"),
                "license": loc.get("license"),
                "version": loc.get("version"),
                "html_only": True,
            }
    return None


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
            headers={"User-Agent": f"Mozilla/5.0 (graphbib; mailto:{DEFAULT_EMAIL})"},
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
        # Sanity check: file should be > 1 KB and start with %PDF
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


def fetch_one(doi, dst, requests, overwrite=False):
    """Process one DOI. Returns a status dict."""
    info = unpaywall_lookup(doi, requests)

    if info.get("_status"):
        s = info["_status"]
        return {"doi": doi, "status": s, "error": info.get("_error", "")}

    if not info.get("is_oa"):
        return {"doi": doi, "status": "paywalled"}

    loc = best_oa_location(info)
    if not loc:
        return {"doi": doi, "status": "oa_no_pdf"}

    if loc.get("html_only"):
        return {
            "doi": doi,
            "status": "oa_landing_page_only",
            "url": loc["url"],
            "host_type": loc.get("host_type"),
        }

    slug = crossref_slug(doi, requests)
    if not slug:
        slug = slugify(doi.replace("/", "-"))
    target = dst / f"{slug}.pdf"

    ok, reason = download_pdf(loc["url"], target, requests, overwrite=overwrite)
    if reason == "exists":
        return {
            "doi": doi,
            "status": "skipped",
            "path": str(target.relative_to(REPO_ROOT)),
        }
    if not ok:
        return {
            "doi": doi,
            "status": "download_failed",
            "reason": reason,
            "url": loc["url"],
        }
    return {
        "doi": doi,
        "status": "fetched",
        "path": str(target.relative_to(REPO_ROOT)),
        "license": loc.get("license"),
        "host_type": loc.get("host_type"),
        "version": loc.get("version"),
    }


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
            # Last-resort regex search inside the token
            m = DOI_RE.search(d)
            if not m:
                continue
            d = m.group(0).rstrip(".,;)").lower()
            if d in seen:
                continue
            seen.add(d)
        out.append(d)
    return out


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
    args = ap.parse_args()

    requests = get_requests()
    dois = collect_dois(args)
    if not dois:
        sys.exit("No DOIs provided. Pass them as args, --from-file, or --from-stdin.")

    if DEFAULT_EMAIL == "contact@example.com":
        print("  ! UNPAYWALL_EMAIL env var not set — using placeholder. "
              "Unpaywall asks for a valid contact email; set yours via "
              "`export UNPAYWALL_EMAIL=you@example.org`.",
              file=sys.stderr)

    dst = Path(args.output_dir).expanduser().resolve()
    dst.mkdir(parents=True, exist_ok=True)

    print(f"  · {len(dois)} DOIs to process → {dst.relative_to(REPO_ROOT) if str(dst).startswith(str(REPO_ROOT)) else dst}",
          file=sys.stderr)

    report = []
    counts = {}
    for i, doi in enumerate(dois, 1):
        result = fetch_one(doi, dst, requests, overwrite=args.overwrite)
        report.append(result)
        counts[result["status"]] = counts.get(result["status"], 0) + 1

        tag = {
            "fetched": "✓",
            "skipped": "·",
            "paywalled": "$",
            "oa_no_pdf": "?",
            "oa_landing_page_only": "?",
            "not_in_unpaywall": "?",
            "invalid_doi": "✗",
            "download_failed": "✗",
            "error": "✗",
        }.get(result["status"], "·")
        suffix = ""
        if result["status"] == "fetched":
            suffix = f" → {result['path']}"
        elif result["status"] == "download_failed":
            suffix = f"  ({result.get('reason', '')})"
        print(f"  {tag} [{i}/{len(dois)}] {doi}{suffix}", file=sys.stderr)
        time.sleep(SLEEP_BETWEEN)

    report_path = dst / "fetch_oa_report.json"
    report_path.write_text(
        json.dumps({"summary": counts, "results": report}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\n=== {len(dois)} processed ===", file=sys.stderr)
    for status, n in sorted(counts.items(), key=lambda t: -t[1]):
        print(f"  {status}: {n}", file=sys.stderr)
    print(f"\nReport: {report_path.relative_to(REPO_ROOT) if str(report_path).startswith(str(REPO_ROOT)) else report_path}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
