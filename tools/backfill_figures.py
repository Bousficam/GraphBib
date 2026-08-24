#!/usr/bin/env python3
"""Back-fill `## Figures` on sources ingested before the figures workflow existed.

Two jobs, deliberately separate because their risk is not the same:

  new     add a `## Figures` section to a source that has none. Purely
          additive: nothing on the page can be lost.
  pages   repair the page references of a section that already exists,
          leaving its titles and captions untouched. Needed because
          sections written before `tools/figure_pairs.py` used marker's
          raw file-name index as if it were the printed page. That index
          is 0-based AND it is the PDF page: an article printed on pages
          111-118 has `_page_3_Figure_2.jpeg` on PDF page 4 and printed
          page 114, where the old sections say `(p. 3)`.

A page reference is only rewritten when the new one is strictly better
(a printed page replacing anything, a PDF page replacing an unknown) -
never the reverse, and never when the tool itself does not know.

The wiki is user content and is not under version control, so every file
this touches is copied to `.maintenance/figures_backfill_backup/` first.

Usage:
    python tools/backfill_figures.py --all                    # dry run
    python tools/backfill_figures.py --all --apply
    python tools/backfill_figures.py --all --mode new --apply
    python tools/backfill_figures.py --source <slug> --apply

Run it under an interpreter that has pymupdf: without it the captions
cannot be located in the PDF and most pages come out unknown.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import figure_pairs as fp  # noqa: E402
from _lib import REPO_ROOT, SRC_DIR  # noqa: E402

BACKUP_DIR = REPO_ROOT / ".maintenance" / "figures_backfill_backup"

# `### Figure 2 - some title (p. 7)` / `(PDF p. 4 - confirm ...)` / `(p. ?)`
HEADING_RE = re.compile(r"^(###\s+.*?)\s*(\((?:PDF\s+)?pp?\.\s*[^)]*\))\s*$", re.I)
IMG_LINE_RE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)")

# Confidence ranking: only ever move a reference up this ladder.
PRINTED, PDF_ONLY, UNKNOWN = 2, 1, 0


def ref_rank(ref: str) -> int:
    r = ref.lower()
    if "?" in r:
        return UNKNOWN
    if "pdf p." in r:
        return PDF_ONLY
    return PRINTED


def rec_rank(rec: dict) -> int:
    if rec.get("printed_page") is not None:
        return PRINTED
    if rec.get("pdf_page") is not None:
        return PDF_ONLY
    return UNKNOWN


def is_stale_marker_ref(old_ref: str, rec: dict) -> bool:
    """Is this reference the known artifact - marker's 0-based index?

    Sections written before `figure_pairs.py` printed the number in the
    file name as if it were a page. marker counts pages from 0, so that
    number is exactly `pdf_page - 1` for the very figure the heading
    points at. When the article starts at printed page 1 a CORRECT
    reference equals `pdf_page`, never `pdf_page - 1`, so the match is
    not ambiguous. Only then is a printed reference overwritten by
    another printed reference.
    """
    m = re.search(r"(\d+)", old_ref)
    if not m or rec.get("pdf_page") is None:
        return False
    return int(m.group(1)) == rec["pdf_page"] - 1


def candidates() -> list:
    """Slugs that have both a wiki source page and an extracted images dir."""
    imgs = {d.name[: -len("_images")] for d in (REPO_ROOT / "raw").rglob("*_images") if d.is_dir()}
    srcs = {p.stem for p in SRC_DIR.rglob("*.md")}
    return sorted(imgs & srcs)


def backup(path: Path) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"{path.stem}.md"
    if not dest.exists():          # keep the ORIGINAL, not the last write
        shutil.copy2(path, dest)


def insert_section(text: str, section: str) -> str:
    """Place `## Figures` where the source templates declare it.

    After the body, before the citation-network sections. Falls back
    through the anchors a page may or may not carry, and appends when it
    carries none.
    """
    for anchor in ("## Cites", "## Cited By", "## Connections",
                   "## Contradictions", "## Extraction Checklist", "## How to Cite"):
        idx = text.find("\n" + anchor)
        if idx != -1:
            return text[: idx + 1] + section.rstrip() + "\n\n" + text[idx + 1:]
    return text.rstrip() + "\n\n" + section.rstrip() + "\n"


def repair_pages(text: str, by_file: dict) -> tuple:
    """Rewrite the page reference of each figure heading. Returns (text, changes).

    A heading is bound to a figure by the image link on the line(s)
    right below it, never by its title: titles are hand-written and do
    not survive matching.
    """
    lines = text.split("\n")
    changes = []
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if not m:
            continue
        rec = None
        for j in range(i + 1, min(i + 4, len(lines))):
            im = IMG_LINE_RE.match(lines[j].strip())
            if im:
                rec = by_file.get(Path(im.group(1)).name)
                break
        if rec is None:
            continue
        new_ref = fp.page_ref(rec)
        old_ref = m.group(2)
        if new_ref == old_ref:
            continue
        better = rec_rank(rec) > ref_rank(old_ref)
        if not (better or is_stale_marker_ref(old_ref, rec)):
            continue
        lines[i] = f"{m.group(1)} {new_ref}"
        changes.append((old_ref, new_ref, rec["file"]))
    return "\n".join(lines), changes


def process(slug: str, mode: str, apply: bool) -> dict:
    data = fp.collect(slug)
    page = SRC_DIR.rglob(f"{slug}.md")
    page = next(iter(sorted(page)), None)
    out = {"slug": slug, "action": "skip", "detail": "", "figures": 0}
    if page is None or not data["images_dir"]:
        out["detail"] = "no source page or no images dir"
        return out

    usable = [f for f in data["figures"] if f["kind"] == "figure"]
    out["figures"] = len(usable)
    text = page.read_text(encoding="utf-8")
    has_section = "## Figures" in text

    if has_section:
        if mode not in ("pages", "both"):
            out["detail"] = "already has ## Figures"
            return out
        by_file = {f["file"]: f for f in data["figures"]}
        new_text, changes = repair_pages(text, by_file)
        if not changes:
            out["action"] = "ok"
            out["detail"] = "page references already correct or not improvable"
            return out
        out["action"] = "pages"
        out["detail"] = f"{len(changes)} page ref(s): " + ", ".join(
            f"{a} -> {b}" for a, b, _ in changes[:3]) + (" ..." if len(changes) > 3 else "")
        if apply:
            backup(page)
            page.write_text(new_text, encoding="utf-8")
        return out

    if mode not in ("new", "both"):
        out["detail"] = "no ## Figures section (mode=pages)"
        return out
    if not usable:
        out["detail"] = "nothing usable to illustrate"
        return out
    section = fp.to_markdown(data)
    if not section:
        out["detail"] = "nothing usable to illustrate"
        return out
    out["action"] = "new"
    printed = sum(1 for f in usable if f["printed_page"] is not None)
    out["detail"] = f"{len(usable)} figures, {printed} with a printed page"
    if apply:
        backup(page)
        page.write_text(insert_section(text, section), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="every source with an images dir")
    g.add_argument("--source", help="one slug")
    ap.add_argument("--mode", choices=["new", "pages", "both"], default="both")
    ap.add_argument("--apply", action="store_true", help="write (default is a dry run)")
    ap.add_argument("--limit", type=int, help="stop after N sources (dry-run sizing)")
    args = ap.parse_args()

    slugs = candidates() if args.all else [args.source.strip().removesuffix(".md")]
    if args.limit:
        slugs = slugs[: args.limit]

    print(f"backfill_figures: {len(slugs)} source(s), mode={args.mode}, "
          f"{'APPLY' if args.apply else 'dry run'}")
    if args.apply:
        print(f"backups -> {BACKUP_DIR.relative_to(REPO_ROOT)}")
    print()

    counts = {}
    for slug in slugs:
        try:
            r = process(slug, args.mode, args.apply)
        except Exception as e:
            r = {"slug": slug, "action": "error", "detail": f"{type(e).__name__}: {e}", "figures": 0}
        counts[r["action"]] = counts.get(r["action"], 0) + 1
        if r["action"] in ("new", "pages", "error"):
            print(f"  [{r['action']:>5}] {slug}: {r['detail']}")

    print()
    print("  " + " | ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 1 if counts.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
