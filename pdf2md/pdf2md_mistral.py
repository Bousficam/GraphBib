#!/usr/bin/env python3
"""Mistral Document AI / OCR - convert PDFs that marker failed on.

Opt-in tier between marker (free, primary) and pymupdf4llm (free, last
resort). Mistral's OCR API handles complex tables, equations, and
scanned PDFs robustly - the corner cases that break Surya inside marker.

Usage
=====

    # Process the entries that marker reported as errors / suspicious
    python pdf2md/pdf2md_mistral.py SRC DST

    # Process specific PDFs (relative paths under SRC)
    python pdf2md/pdf2md_mistral.py SRC DST --files Fatigue/borghini2014.pdf

    # Skip files already covered by Mistral in a previous run
    # (default: idempotent - already-converted .md files are skipped)
    python pdf2md/pdf2md_mistral.py SRC DST --force   # re-run anyway

    # Retry pass over what marker failed on, instead of the whole tree:
    python pdf2md/pdf2md_mistral.py SRC DST --from-marker-report

API key
=======

The free experimental plan is enough for retry-on-marker-failure usage.
Get one at https://console.mistral.ai.

The key is looked up in this order, first hit wins:

    1. $MISTRAL_API_KEY in the environment
    2. MISTRAL_API_KEY= in the repo's gitignored `.env`
    3. the macOS keychain (`security find-generic-password -s MISTRAL_API_KEY`)
    4. a hidden prompt, ONLY when stdin is a terminal

With no key and no terminal to ask on - which is every run launched by
the agent - the script exits with code 3 and says so on stderr. That
code means "ask the user for a key", NOT "this PDF cannot be
converted": callers must not fall back to another backend on it. See
`docs/workflows/conversion.md`.

Cost
====

Mistral charges per page; the experimental plan is free with rate
limits. The script paces itself at ~2 requests/second by default
(--sleep override). On a 698-PDF corpus, expect ~10-20 % to need
Mistral (the entries marker errored on or produced suspicious output
for) → ~70-140 PDFs through the API.

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
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

API_URL = "https://api.mistral.ai/v1/ocr"
DEFAULT_MODEL = "mistral-ocr-latest"
DEFAULT_SLEEP = 0.5   # 2 req/s - polite for the experimental plan
DEFAULT_TIMEOUT = 180  # 3 min per PDF


# Exit code reserved for "no key was found anywhere". Distinct from a
# conversion failure so a caller can tell the two apart: a missing key is
# answered by asking the user, never by falling back to another backend.
EXIT_NO_KEY = 3

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
KEYCHAIN_SERVICE = "MISTRAL_API_KEY"


def key_from_env_file(path=None):
    """MISTRAL_API_KEY from the repo's gitignored `.env`, or None.

    Parsed here rather than imported from tools/_lib so that pdf2md stays
    runnable on its own. A key sitting in `.env` used to be invisible to
    this script, which then reported "no key" while the key was right
    there - the failure this exists to prevent.
    """
    try:
        text = (path or ENV_FILE).read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == "MISTRAL_API_KEY":
            return value.strip().strip("'\"") or None
    return None


def key_from_keychain(service=KEYCHAIN_SERVICE):
    """The key from the macOS keychain, or None. Never raises."""
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out or None


def get_api_key():
    """Resolve the Mistral key, or exit EXIT_NO_KEY telling the caller to ask.

    Order: environment, repo `.env`, macOS keychain, hidden prompt. The
    prompt is only offered when stdin is a terminal; an agent-launched
    run has no terminal, so it exits with a message the agent is meant
    to act on by asking the user for a key - not by switching backend.
    """
    for source, key in (
        ("environment", os.getenv("MISTRAL_API_KEY")),
        (f"{ENV_FILE.name} file", key_from_env_file()),
        ("macOS keychain", key_from_keychain()),
    ):
        if key and key.strip():
            if source != "environment":
                # `log` is set up inside main(); this runs before that.
                print(f"MISTRAL_API_KEY read from the {source}.", file=sys.stderr)
            return key.strip()

    print("", file=sys.stderr)
    print("MISTRAL_API_KEY not found in the environment, in .env, "
          "or in the macOS keychain.", file=sys.stderr)
    print("-> Get a free experimental key at https://console.mistral.ai",
          file=sys.stderr)
    print("-> Then either: export MISTRAL_API_KEY=...", file=sys.stderr)
    print("             or: add MISTRAL_API_KEY=... to .env (gitignored)",
          file=sys.stderr)
    print("", file=sys.stderr)

    if not sys.stdin.isatty():
        print("No terminal to prompt on. ASK THE USER for a key and retry - "
              "do NOT fall back to another backend, Mistral is the default "
              "converter (docs/workflows/conversion.md).", file=sys.stderr)
        sys.exit(EXIT_NO_KEY)

    try:
        key = getpass.getpass("Paste your MISTRAL_API_KEY (input hidden): ").strip()
    except (EOFError, KeyboardInterrupt):
        key = ""
    if not key:
        print("No API key provided.", file=sys.stderr)
        sys.exit(EXIT_NO_KEY)
    return key


def mistral_ocr(pdf_path, api_key, model=DEFAULT_MODEL, timeout=DEFAULT_TIMEOUT,
                want_images=True):
    """Send a PDF to Mistral OCR. Returns (markdown_text, images, error_or_None).

    `images` maps the image id used in the markdown (e.g. "img-3.jpeg") to its
    raw bytes. The OCR always names its figures in the markdown, but it only
    ships the bytes when include_image_base64 is requested; asking for them is
    what makes the `![img-N.jpeg]` references resolve to real files instead of
    dangling. Mistral also detects vector-drawn figures, which is why this is
    preferred over pulling embedded bitmaps out of the PDF afterwards.
    """
    try:
        b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
    except Exception as e:
        return None, {}, f"read-error: {e!r}"

    payload = {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{b64}",
        },
        "include_image_base64": bool(want_images),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(API_URL, json=payload, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as e:
        return None, {}, f"request-error: {type(e).__name__}: {e}"

    if r.status_code == 401:
        return None, {}, "auth-error: invalid MISTRAL_API_KEY"
    if r.status_code == 429:
        return None, {}, "rate-limited: 429 (consider increasing --sleep)"
    if r.status_code >= 400:
        return None, {}, f"http-{r.status_code}: {r.text[:200]}"

    try:
        data = r.json()
    except ValueError:
        return None, {}, "non-json response"

    pages = data.get("pages") or []
    if not pages:
        return None, {}, "no pages in response"

    parts, images = [], {}
    for p in pages:
        md = p.get("markdown")
        if md is None:
            md = p.get("content") or ""  # API field name fallback
        if md:
            parts.append(md)
        for im in (p.get("images") or []):
            name = im.get("id") or im.get("image_name")
            blob = im.get("image_base64")
            if not name or not blob:
                continue
            # the API may hand back a full data: URI rather than bare base64
            if "," in blob and blob.lstrip().startswith("data:"):
                blob = blob.split(",", 1)[1]
            try:
                images[name] = base64.b64decode(blob)
            except Exception:
                continue
    if not parts:
        return None, images, "empty markdown across all pages"

    return "\n\n".join(parts), images, None


def scan_targets(src, dst, force=False):
    """Every PDF under SRC, mirrored into DST. Returns the same shape as
    `collect_targets`.

    This is what "Mistral is the default converter" means in practice.
    The script used to have no way to express it: without --files it
    required a marker_report.json and refused to start, so a
    Mistral-first run was impossible and the pipeline silently became
    marker-first - the slow backend - whatever the docs said.

    Already-converted files are skipped unless `force`, so a re-run
    costs nothing.
    """
    targets = []
    for pdf in sorted(src.rglob("*.pdf")):
        if pdf.name.startswith("."):
            continue
        rel = pdf.relative_to(src)
        md = (dst / rel).with_suffix(".md")
        if not force and already_mistral(md):
            continue
        targets.append({"pdf": pdf, "rel_md": md, "reason": "scan"})
    return targets


def collect_targets(report_path, src, dst, only_files=None):
    """The PDFs marker failed on, from marker_report.json. Returns dicts
    of {pdf, rel_md, reason}.

    This is the RETRY pass (`--from-marker-report`), not the default:
    see `scan_targets`.
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
    ap.add_argument("--from-marker-report", action="store_true",
                    help="Retry pass: convert only what marker errored on or "
                         "produced suspicious output for, per DST/marker_report.json. "
                         "Without this flag every PDF under SRC is converted, which "
                         "is the default Mistral-first pipeline.")
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
    ap.add_argument("--no-images", action="store_true",
                    help="Do not request figure images (smaller, faster responses)")
    ap.add_argument("--images-only", action="store_true",
                    help="Write only the <stem>_images/ directory and leave an "
                         "existing .md untouched. Use on sources already "
                         "ingested, where re-OCR must not alter the text the "
                         "wiki was built from.")
    args = ap.parse_args()

    if args.images_only and args.no_images:
        sys.exit("--images-only and --no-images are mutually exclusive.")

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

    if args.files:
        targets = collect_targets(dst / "marker_report.json", src, dst,
                                  only_files=args.files)
    elif args.from_marker_report:
        targets = collect_targets(dst / "marker_report.json", src, dst)
    else:
        targets = scan_targets(src, dst, force=args.force)
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

        # --images-only revisits sources on purpose, so the "already converted"
        # guard would otherwise skip exactly the files we came back for.
        if not args.force and not args.images_only and already_mistral(md_path):
            stats["skipped"].append({"pdf": str(rel), "reason": "already Mistral"})
            log.info("  · already Mistral-converted, skipping")
            continue

        md_text, images, err = mistral_ocr(
            pdf, api_key, model=args.model, timeout=args.timeout,
            want_images=not args.no_images)
        if err and not (args.images_only and images):
            stats["errors"].append({"pdf": str(rel), "error": err})
            log.warning(f"  ✗ {err}")
            time.sleep(args.sleep)
            continue

        md_path.parent.mkdir(parents=True, exist_ok=True)

        n_img = 0
        if images:
            img_dir = md_path.with_name(md_path.stem + "_images")
            img_dir.mkdir(parents=True, exist_ok=True)
            for name, blob in images.items():
                # the id doubles as the markdown link target, so keep it verbatim
                (img_dir / Path(name).name).write_bytes(blob)
                n_img += 1

        if args.images_only:
            stats["ok"].append({"pdf": str(rel), "images": n_img,
                                "md": "left untouched"})
            log.info(f"  ✓ {n_img} image(s) -> {md_path.stem}_images/ (MD untouched)")
            time.sleep(args.sleep)
            continue

        header = (
            f"---\nsource_pdf: {pdf}\ntitle: {pdf.stem}\n"
            f"backend: mistral\nfallback_from: {t['reason']}\n---\n\n"
        )
        md_path.write_text(header + md_text, encoding="utf-8")
        stats["ok"].append({"pdf": str(rel), "chars": len(md_text), "images": n_img})
        log.info(f"  ✓ wrote {md_path.relative_to(dst)} "
                 f"({len(md_text)} chars, {n_img} image(s))")
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
