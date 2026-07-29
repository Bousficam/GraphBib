#!/usr/bin/env python3
"""
Sci-Hub batch fetcher via sci-hub.fr.
Uses Playwright (headed) to get DDoS-Guard cookies once,
then downloads PDFs via plain requests for all DOIs.

Usage:
    python tools/fetch_scihub.py \
        --from-report project-review/<name>/screening/1st-pass/raw/fetch_oa_report.json \
        --output-dir  project-review/<name>/screening/1st-pass/raw/ \
        [--statuses paywalled download_failed] \
        [--delay 1.5] [--limit N]
"""
import argparse, json, re, time, sys
from pathlib import Path
from urllib.parse import quote

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("pip install requests beautifulsoup4")

SCIHUB_BASE  = "https://sci-hub.fr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

SESSION_COOKIES = [
    {"name": "refresh", "value": "1780316081.6382", "domain": ".sci-hub.fr", "path": "/"},
    {"name": "session", "value": "f146edb14cf3886588b6d35942b27ebc", "domain": ".sci-hub.fr", "path": "/"},
]


def get_verified_cookies():
    """Open headed Chromium once to solve DDoS-Guard challenge, return full cookie dict."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("pip install playwright && python -m playwright install chromium")

    print("Opening Chrome to get verified session cookies (window will appear briefly)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="fr-FR",
        )
        ctx.add_cookies(SESSION_COOKIES)
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        page = ctx.new_page()
        page.goto(f"{SCIHUB_BASE}/", wait_until="domcontentloaded", timeout=20000)
        try:
            page.wait_for_function(
                "!document.title.toLowerCase().includes('robot')",
                timeout=15000
            )
        except Exception:
            pass
        time.sleep(2)
        cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        browser.close()
    print(f"Got {len(cookies)} cookies: {list(cookies.keys())}")
    return cookies


def find_pdf_url(html: str):
    """Extract PDF URL from Sci-Hub page HTML."""
    # Pattern 1: /storage/... .pdf
    m = re.search(r'["\'](/storage/[^\s"\'<>]+\.pdf[^\s"\'<>]*)["\']', html)
    if m:
        return SCIHUB_BASE + m.group(1)
    # Pattern 2: //sci-hub.*/storage/...
    m = re.search(r'(//sci-hub\.[a-z.]+/storage/[^\s"\'<>]+\.pdf[^\s"\'<>]*)', html)
    if m:
        return "https:" + m.group(1)
    # Pattern 3: iframe/embed src with pdf
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["iframe", "embed"]):
        src = tag.get("src", "")
        if src and (".pdf" in src.lower() or "storage" in src.lower()):
            if src.startswith("//"):
                return "https:" + src
            if src.startswith("/"):
                return SCIHUB_BASE + src
            return src
    return None


def slug_from_doi(doi: str) -> str:
    return re.sub(r"[^\w\-]", "-", doi).strip("-")


def fetch_doi(session: requests.Session, doi: str, out_dir: Path) -> dict:
    url = f"{SCIHUB_BASE}/{quote(doi, safe='/:')}"
    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()
    except Exception as e:
        return {"doi": doi, "status": "error", "reason": str(e)[:120]}

    pdf_url = find_pdf_url(r.text)
    if not pdf_url:
        # Check if it's a clean article page (no robot challenge, no PDF found = not indexed)
        if "robot" in r.text.lower() and len(r.text) < 10000:
            return {"doi": doi, "status": "scihub_challenge", "reason": "bot challenge still active"}
        return {"doi": doi, "status": "scihub_not_indexed", "reason": "no PDF found in page"}

    try:
        pr = session.get(pdf_url, timeout=60, stream=True)
        pr.raise_for_status()
        ct = pr.headers.get("content-type", "")
        if "pdf" not in ct.lower() and not pdf_url.endswith(".pdf"):
            return {"doi": doi, "status": "scihub_not_pdf", "reason": f"content-type={ct}"}
        slug = slug_from_doi(doi)
        out_path = out_dir / f"{slug}.pdf"
        with open(out_path, "wb") as f:
            for chunk in pr.iter_content(8192):
                f.write(chunk)
        return {"doi": doi, "status": "fetched_scihub", "path": str(out_path)}
    except Exception as e:
        return {"doi": doi, "status": "scihub_download_failed", "reason": str(e)[:120]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-report", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--statuses", nargs="+",
                    default=["paywalled", "download_failed"])
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report = json.load(open(args.from_report))
    results = report.get("results", [])
    targets = [r["doi"] for r in results if r.get("status") in args.statuses]
    if args.limit:
        targets = targets[:args.limit]

    print(f"Sci-Hub fetch: {len(targets)} DOIs ({', '.join(args.statuses)})")

    # Get verified session cookies once
    cookies = get_verified_cookies()

    session = requests.Session()
    session.headers.update(HEADERS)
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="sci-hub.fr")

    scihub_results = []
    fetched = failed = skipped = 0

    for i, doi in enumerate(targets, 1):
        slug = slug_from_doi(doi)
        if (out_dir / f"{slug}.pdf").exists():
            print(f"  ~ [{i}/{len(targets)}] already exists: {slug}.pdf")
            scihub_results.append({"doi": doi, "status": "skipped_exists"})
            skipped += 1
            continue

        result = fetch_doi(session, doi, out_dir)
        scihub_results.append(result)

        if result["status"] == "fetched_scihub":
            fetched += 1
            print(f"  ✓ [{i}/{len(targets)}] {doi} → {Path(result['path']).name}")
        else:
            failed += 1
            reason = result.get("reason", "")[:60]
            print(f"  ✗ [{i}/{len(targets)}] {doi} - {result['status']}: {reason}")
            # If bot challenge persists, re-acquire cookies
            if result["status"] == "scihub_challenge" and i % 20 == 0:
                print("  ↻ Re-acquiring cookies...")
                cookies = get_verified_cookies()
                for name, value in cookies.items():
                    session.cookies.set(name, value, domain="sci-hub.fr")

        if i < len(targets):
            time.sleep(args.delay)

    # Save report
    report_path = out_dir / "fetch_scihub_report.json"
    json.dump({
        "summary": {"fetched": fetched, "failed": failed,
                    "skipped": skipped, "total": len(targets)},
        "results": scihub_results,
    }, open(report_path, "w"), indent=2)

    print(f"\n✓ Done: {fetched} fetched, {failed} failed, {skipped} skipped")
    print(f"  Report: {report_path}")


if __name__ == "__main__":
    main()
