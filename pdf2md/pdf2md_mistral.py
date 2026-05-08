#!/usr/bin/env python3
"""Mistral Document AI / OCR — convert PDFs that marker failed on.

Opt-in tier between marker (free, primary) and pymupdf4llm (free, last
resort). Mistral's OCR API handles complex tables, equations, and
scanned PDFs robustly — the corner cases that break Surya inside marker.

Usage
=====

    # Process the entries that marker reported as errors / suspicious
    python pdf2md/pdf2md_mistral.py SRC DST

    # Process specific PDFs (relative paths under SRC)
    python pdf2md/pdf2md_mistral.py SRC DST --files Fatigue/borghini2014.pdf

    # Skip files already covered by Mistral in a previous run
    # (default: idempotent — already-converted .md files are skipped)
    python pdf2md/pdf2md_mistral.py SRC DST --force   # re-run anyway

API key
=======

The free experimental plan is enough for retry-on-marker-failure usage.
Get one at https://console.mistral.ai. Set MISTRAL_API_KEY in your env
or the script will prompt for it (input hidden).

Cost
====

Mistral charges per page; the experimental plan is free with rate
limits. The script paces itself at ~2 requests/second by default
(--sleep override). On a 698-PDF corpus, expect ~10–20 % to need
Mistral (the entries marker errored on or produced suspicious output
for) → ~70–140 PDFs through the API.

Output
======

For each processed PDF, writes the same path under DST (mirroring SRC
arborescence) with frontmatter:

    ---
    source_pdf: <abs path>
    title: <pdf stem>
    backend: mistral
    fallback_from: <error|suspicious|forced>
    ---

    <markdown content from Mistral>

Writes mistral_report.json (ok / errors / skipped / total) alongside.
"""
import argparse
import base64
import getpass
import json
import logging
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

API_URL = "https://api.mistral.ai/v1/ocr"
DEFAULT_MODEL = "mistral-ocr-latest"
DEFAULT_SLEEP = 0.5   # 2 req/s — polite for the experimental plan
DEFAULT_TIMEOUT = 180  # 3 min per PDF


def get_api_key():
    """Resolve MISTRAL_API_KEY from env, or prompt the user with a hidden input."""
    key = os.getenv("MISTRAL_API_KEY")
    if key:
        return key
    print("", file=sys.stderr)
    print("MISTRAL_API_KEY is not set in your environment.", file=sys.stderr)
    print("→ Get a free experimental key at https://console.mistral.ai",
          file=sys.stderr)
    print("→ Or export it: export MISTRAL_API_KEY=…", file=sys.stderr)
    print("", file=sys.stderr)
    try:
        key = getpass.getpass("Paste your MISTRAL_API_KEY (input hidden): ").strip()
    except EOFError:
        sys.exit("No API key provided. Aborting.")
    if not key:
        sys.exit("No API key provided. Aborting.")
    return key


def mistral_ocr(pdf_path, api_key, model=DEFAULT_MODEL, timeout=DEFAULT_TIMEOUT):
    """Send a PDF to Mistral OCR. Returns (markdown_text, error_or_None)."""
    try:
        b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
    except Exception as e:
        return None, f"read-error: {e!r}"

    payload = {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{b64}",
        },
        "include_image_base64": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(API_URL, json=payload, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as e:
        return None, f"request-error: {type(e).__name__}: {e}"

    if r.status_code == 401:
        return None, "auth-error: invalid MISTRAL_API_KEY"
    if r.status_code == 429:
        return None, "rate-limited: 429 (consider increasing --sleep)"
    if r.status_code >= 400:
        return None, f"http-{r.status_code}: {r.text[:200]}"

    try:
        data = r.json()
    except ValueError:
        return None, "non-json response"

    pages = data.get("pages") or []
    if not pages:
        return None, "no pages in response"

    parts = []
    for p in pages:
        md = p.get("markdown")
        if md is None:
            md = p.get("content") or ""  # API field name fallback
        if md:
            parts.append(md)
    if not parts:
        return None, "empty markdown across all pages"

    return "\n\n".join(parts), None


def collect_targets(report_path, src, dst, only_files=None):
    """Read marker_report.json (and optionally fallback_report.json) to
    determine which PDFs need Mistral. Returns list of dicts with
    {pdf, rel_md, reason}.
    """
    targets = []

    if only_files:
        for rel in only_files:
            rel_path = Path(rel)
            pdf = src / rel_path
            md = (dst / rel_path).with_suffix(".md")
            targets.append({"pdf": pdf, "rel_md": md, "reason": "user-specified"})
        return targets

    if not report_path.exists():
        sys.exit(f"No marker report found at {report_path}. "
                 "Run pdf2md/pdf2md_marker.py first or use --files.")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    seen = set()
    for entry in report.get("errors", []):
        rel_md = Path(entry["pdf"])
        if str(rel_md) in seen:
            continue
        seen.add(str(rel_md))
        pdf = src / rel_md.with_suffix(".pdf")
        targets.append({"pdf": pdf, "rel_md": dst / rel_md, "reason": "marker-error"})
    for entry in report.get("suspicious", []):
        rel_md = Path(entry["pdf"])
        if str(rel_md) in seen:
            continue
        seen.add(str(rel_md))
        pdf = src / rel_md.with_suffix(".pdf")
        targets.append({"pdf": pdf, "rel_md": dst / rel_md, "reason": "marker-suspicious"})
    return targets


def already_mistral(md_path):
    """True if the MD already exists with `backend: mistral` in its frontmatter."""
    if not md_path.is_file():
        return False
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return False
    if not text.startswith("---\n"):
        return False
    end = text.find("\n---\n", 4)
    if end == -1:
        return False
    fm = text[4:end]
    return "backend: mistral" in fm


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src", help="Source directory (root of the PDF library)")
    ap.add_argument("dst", help="Destination directory for converted .md")
    ap.add_argument("--files", nargs="+",
                    help="Specific PDFs (relative to SRC) to process; "
                         "skips reading marker_report.json")
    ap.add_argument("--force", action="store_true",
                    help="Re-run even if the MD is already Mistral-converted")
    ap.add_argument("--sleep", type=float, default=DEFAULT_SLEEP,
                    help=f"Seconds between API calls (default {DEFAULT_SLEEP})")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"Mistral OCR model (default {DEFAULT_MODEL})")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"Per-PDF API timeout in seconds (default {DEFAULT_TIMEOUT})")
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    dst = Path(args.dst).expanduser().resolve()
    if not src.is_dir():
        sys.exit(f"SRC is not a directory: {src}")
    dst.mkdir(parents=True, exist_ok=True)

    log_path = dst / "mistral.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stderr)],
    )
    log = logging.getLogger("mistral")

    marker_report = dst / "marker_report.json"
    targets = collect_targets(marker_report, src, dst, only_files=args.files)
    if not targets:
        log.info("No targets to process.")
        return

    api_key = get_api_key()
    log.info(f"{len(targets)} PDF(s) to process via Mistral OCR (model={args.model})")

    stats = {"ok": [], "skipped": [], "errors": [], "missing": []}
    report_path = dst / "mistral_report.json"

    for i, t in enumerate(targets, 1):
        pdf = t["pdf"]
        md_path = t["rel_md"]
        rel = pdf.relative_to(src) if pdf.is_relative_to(src) else pdf
        log.info(f"[{i}/{len(targets)}] {rel} ({t['reason']})")

        if not pdf.is_file():
            stats["missing"].append({"pdf": str(rel), "reason": "PDF source not found"})
            log.warning(f"  ! source PDF missing: {pdf}")
            continue

        if not args.force and already_mistral(md_path):
            stats["skipped"].append({"pdf": str(rel), "reason": "already Mistral"})
            log.info("  · already Mistral-converted, skipping")
            continue

        md_text, err = mistral_ocr(pdf, api_key, model=args.model, timeout=args.timeout)
        if err:
            stats["errors"].append({"pdf": str(rel), "error": err})
            log.warning(f"  ✗ {err}")
            time.sleep(args.sleep)
            continue

        md_path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"---\nsource_pdf: {pdf}\ntitle: {pdf.stem}\n"
            f"backend: mistral\nfallback_from: {t['reason']}\n---\n\n"
        )
        md_path.write_text(header + md_text, encoding="utf-8")
        stats["ok"].append({"pdf": str(rel), "chars": len(md_text)})
        log.info(f"  ✓ wrote {md_path.relative_to(dst)} ({len(md_text)} chars)")
        time.sleep(args.sleep)

    stats["summary"] = {
        "total": len(targets),
        "ok": len(stats["ok"]),
        "skipped": len(stats["skipped"]),
        "errors": len(stats["errors"]),
        "missing": len(stats["missing"]),
    }
    report_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    log.info(f"=== {stats['summary']} ===")
    log.info(f"Report: {report_path}")


if __name__ == "__main__":
    main()
