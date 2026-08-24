#!/usr/bin/env python3
"""Pair one source's extracted images with their captions and pages.

The deterministic half of building a `## Figures` section. It does not
judge relevance - it resolves the three things an agent cannot guess
reliably from the file names:

    1. which caption belongs to which image (multi-panel runs included),
    2. what page the figure is on, across BOTH converter conventions,
    3. the relative path from the wiki source page down to the image.

Converter conventions, both of which exist in the corpus:

    marker    _page_3_Figure_2.jpeg    page index in the file name (0-based)
    Mistral   img-7.jpeg               no page in the name at all

Mistral is the default backend, so a page-from-filename rule alone
covers a minority of sources. When the name carries nothing, the page is
read from the converted markdown's own page anchors ("Page 4 of 44" and
friends) at the line where the image is referenced. When neither exists
the page is reported as unknown rather than guessed - the citation rule
allows `(p. ?)`, it does not allow a number nobody checked.

Pairing reuses `build_figure_index.captions_for`, which already handles
the case that breaks naive matching: an OCR emits one image per panel,
so a multi-panel figure is a RUN of image references followed by a
single caption.

Usage:
    python tools/figure_pairs.py --source <slug>
    python tools/figure_pairs.py --source <slug> --json
    python tools/figure_pairs.py --source <slug> --markdown   # ready to paste
    python tools/figure_pairs.py --source <slug> --markdown --include-noise

Exit code 0 when at least one figure is usable, 1 when there is nothing
to illustrate (no images dir, or everything classified as page
furniture) - so a caller can branch without parsing the output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, SRC_DIR, parse_fm  # noqa: E402
from build_figure_index import IMG_REF, captions_for, dedash  # noqa: E402
from crossref import crossref_metadata, normalize_doi  # noqa: E402

# Page anchors the converters leave as running headers. Same family as
# tools/verify_ingest.py - a sparse map is not trusted.
PAGE_MARKERS = [
    re.compile(r"^\s*Page\s+(\d+)\s+of\s+\d+\s*$", re.I),
    re.compile(r"^\s*<!--\s*page\s*[:=]?\s*(\d+)\s*-->\s*$", re.I),
    re.compile(r"^\s*\[?page\s+(\d+)\]?\s*$", re.I),
    re.compile(r"^\s*-{2,}\s*page\s+(\d+)\s*-{2,}\s*$", re.I),
]

MARKER_PAGE_RE = re.compile(r"_page_(\d+)_", re.I)
TABLE_CAPTION_RE = re.compile(r"^\s*\**\s*Tab(?:le|\.)\s*\d+", re.I)

# A caption-less image that is byte-identical in size to two others is a
# logo or a rule; a source whose images are overwhelmingly caption-less
# is a scan the OCR segmented into page furniture.
REPEAT_THRESHOLD = 3
BULK_MIN_FILES = 60
BULK_CAPTION_RATIO = 0.2
# When no converter gave us a page at all, an uncaptioned image referenced
# this early in the markdown is title-page furniture (journal logo, ORCID
# badge, open-access banner).
TITLE_AREA_LINES = 40


def norm_for_search(text: str) -> str:
    """Fold OCR text and PDF text onto the same alphabet.

    The converted markdown and the PDF text layer disagree on ligatures
    ('fi' vs the single glyph), on hyphenation and on whitespace, so a
    literal substring search finds nothing. Reduce both to lowercase
    alphanumerics separated by single spaces.
    """
    t = (text or "").lower().replace("\ufb01", "fi").replace("\ufb02", "fl")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def pdf_page_texts(pdf_path: Path):
    """Normalized text of each PDF page, or None when unavailable.

    pymupdf is optional: it is not installed in every environment this
    repo runs under, and a missing import must degrade the page to
    unknown rather than crash the ingest.
    """
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            return None
    try:
        doc = pymupdf.open(str(pdf_path))
        return [norm_for_search(doc[i].get_text()) for i in range(doc.page_count)]
    except Exception:
        return None


def locate_caption(caption: str, pages: list, words: int = 8):
    """1-based PDF page holding this caption, or None.

    Only a UNIQUE hit counts: a key matching two pages (a running header,
    a caption repeated in a supplement) locates nothing, and no page
    beats a wrong page.

    Two keys are tried. The head of the caption usually works; when it
    does not - the OCR dropped the opening words, or the PDF hyphenated
    across a line the normalizer cannot rejoin - a slice taken from the
    middle is tried, which fails differently.
    """
    toks = norm_for_search(caption).split()
    keys = [" ".join(toks[:words])]
    if len(toks) >= words * 2:
        mid = len(toks) // 2
        keys.append(" ".join(toks[mid:mid + words]))
    for key in keys:
        if len(key) < 20:
            continue
        hits = [i + 1 for i, txt in enumerate(pages) if key in txt]
        if len(hits) == 1:
            return hits[0]
    return None


def resolve_pdf(fm: dict, raw: Path):
    """The article PDF, which often lives outside the repo.

    `source_pdf` usually points at the master copy in the user's library
    (see audit_raw's `external` status). It is read, never written.
    """
    val = str((fm or {}).get("source_pdf") or "").strip()
    if val:
        cand = Path(val).expanduser()
        if not cand.is_absolute():
            cand = REPO_ROOT / cand
        if cand.is_file():
            return cand
    cand = raw.with_suffix(".pdf") if raw else None
    return cand if cand and cand.is_file() else None


def printed_page_offset(fm: dict, max_pdf_page: int):
    """(first printed page, how it was established) or (None, None).

    Two pagination regimes, and the article's Crossref record says which:

    - a **page range** ("111-118"): the article is an offprint inside a
      journal issue, so printed page = first + pdf page - 1. Refused when
      the range does not cover the pages the figures claim (a supplement
      bundled into the same PDF, a wrong DOI).
    - an **article number** ("118824", modern Elsevier / Frontiers /
      PLOS): each article paginates from 1, so the PDF page IS the
      printed page. Recognized by the absence of a dash together with a
      long value or an `article_number` in the frontmatter - not by a
      short single number, which is a genuine one-page article.

    Anything else returns None: better an honest unknown than a page
    number derived from a rule that does not apply.
    """
    doi = normalize_doi(str(fm.get("doi") or ""))
    if not doi:
        return None, None
    try:
        md = crossref_metadata(doi)
    except Exception:
        return None, None
    rng = ((md or {}).get("pages") or "").strip()
    if not rng:
        return None, None

    m = re.match(r"^(\d+)\s*-\s*(\d+)$", rng)
    if m:
        first, last = int(m.group(1)), int(m.group(2))
        if last >= first and (last - first + 1) >= max_pdf_page:
            return first, "range"
        return None, None

    if re.fullmatch(r"\d+", rng) and (len(rng) >= 5 or fm.get("article_number")):
        return 1, "article-number"
    return None, None


def build_page_map(raw_text: str):
    """line index -> printed page number, or None when too sparse to trust."""
    lines = raw_text.splitlines()
    best = []
    for rx in PAGE_MARKERS:
        hits = [(i, int(m.group(1))) for i, ln in enumerate(lines) if (m := rx.match(ln))]
        if len(hits) > len(best):
            best = hits
    if not best or len(best) < max(3, len(lines) // 200):
        return None
    page_of, idx, current = {}, 0, best[0][1]
    for i in range(len(lines)):
        while idx < len(best) and best[idx][0] <= i:
            current = best[idx][1]
            idx += 1
        page_of[i] = current
    return page_of


def clean_caption(text: str) -> str:
    """Drop the bold markers the OCR leaves when a caption reads '**Fig. 1.**'.

    `captions_for` strips the 'Fig. N.' label but not the closing '**'
    that followed it, so a caption often starts with '** '.
    """
    return re.sub(r"^[*:.\s]+", "", text or "").strip()


def image_lines(raw_text: str) -> dict:
    """image file name -> line index of its first reference in the markdown."""
    out = {}
    for i, line in enumerate(raw_text.splitlines()):
        for m in IMG_REF.finditer(line):
            name = Path(m.group(1)).name
            out.setdefault(name, i)
    return out


def resolve_paths(slug: str, raw_override: str = None):
    """(wiki source page, converted markdown, images dir) for a slug.

    The converted markdown is named by the page's `source_file:` pointer
    (kept accurate by `tools/audit_raw.py`), with a search under `raw/`
    as the fallback. The images dir is `<stem>_images/` beside it.
    """
    hits = sorted(SRC_DIR.rglob(f"{slug}.md"))
    page = hits[0] if hits else None

    raw = None
    if raw_override:
        raw = Path(raw_override).expanduser()
    elif page is not None:
        fm, _ = parse_fm(page.read_text(encoding="utf-8"))
        for key in ("source_file", "source_md"):
            val = str((fm or {}).get(key) or "").strip()
            if val:
                cand = Path(val)
                if not cand.is_absolute():
                    cand = REPO_ROOT / cand
                if cand.is_file() and cand.suffix.lower() == ".md":
                    raw = cand
                    break
    if raw is None:
        found = sorted((REPO_ROOT / "raw").rglob(f"{slug}.md"))
        raw = found[0] if found else None

    img_dir = raw.with_name(raw.stem + "_images") if raw else None
    return page, raw, (img_dir if img_dir and img_dir.is_dir() else None)


def collect(slug: str, raw_override: str = None, use_pdf: bool = True) -> dict:
    page, raw, img_dir = resolve_paths(slug, raw_override)
    out = {
        "slug": slug,
        "source_page": str(page.relative_to(REPO_ROOT)) if page else None,
        "article": str(raw.relative_to(REPO_ROOT)) if raw and REPO_ROOT in raw.parents else (str(raw) if raw else None),
        "images_dir": str(img_dir.relative_to(REPO_ROOT)) if img_dir else None,
        "has_figures_section": bool(page and "## Figures" in page.read_text(encoding="utf-8")),
        "page_map": False,
        "figures": [],
    }
    if img_dir is None or raw is None:
        return out

    raw_text = raw.read_text(encoding="utf-8", errors="replace")
    caps = captions_for(raw)
    lines_of = image_lines(raw_text)
    page_map = build_page_map(raw_text)
    out["page_map"] = page_map is not None
    md_lines = raw_text.splitlines()

    files = [f for f in sorted(img_dir.iterdir())
             if f.is_file() and not f.name.startswith(".")]

    by_size = {}
    for f in files:
        by_size.setdefault(f.stat().st_size, []).append(f.name)
    repeated = {n for names in by_size.values() if len(names) >= REPEAT_THRESHOLD
                for n in names}
    bulk_noise = len(files) >= BULK_MIN_FILES and len(caps) < len(files) * BULK_CAPTION_RATIO

    # A marker file name gives a PDF page; Crossref gives the printed range,
    # and the two together give the printed page.
    fm_page = {}
    if page is not None:
        fm_page, _ = parse_fm(page.read_text(encoding="utf-8"))
    # Mistral file names carry no page at all, so for those the page comes
    # from the PDF text layer: a caption is a distinctive string, and the
    # page it sits on is the page the figure is on.
    pdf_path = resolve_pdf(fm_page, raw) if use_pdf else None
    pdf_texts = pdf_page_texts(pdf_path) if pdf_path else None
    out["pdf"] = str(pdf_path) if pdf_path else None
    out["pdf_text"] = pdf_texts is not None

    seen_hash = {}
    for f in files:
        c = caps.get(f.name, {})
        caption = clean_caption(c.get("caption", ""))
        fig, panel, part = c.get("fig", ""), c.get("panel", ""), c.get("part", "")
        label = (f"Figure {fig}{panel.upper()}" + (f" (panel {part[1:]})" if part else "")) \
            if fig else "unlabelled"

        line_idx = lines_of.get(f.name)
        pdf_page = None
        m = MARKER_PAGE_RE.search(f.name)
        if m:
            # marker numbers pages from 0; the PDF page a human counts is +1.
            # This is the PDF page, which equals the printed page only when
            # the article starts at page 1 (not the case for supplements).
            pdf_page = int(m.group(1)) + 1
        if pdf_page is None and pdf_texts and caption:
            pdf_page = locate_caption(caption, pdf_texts)
        printed_page = page_map.get(line_idx) if (page_map and line_idx is not None) else None

        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        duplicate_of = seen_hash.get(digest)
        seen_hash.setdefault(digest, f.name)

        first_page = (
            pdf_page == 1
            or printed_page == 1
            or (pdf_page is None and printed_page is None
                and line_idx is not None and line_idx < TITLE_AREA_LINES)
        )

        is_table = False
        if line_idx is not None:
            for j in range(line_idx + 1, min(line_idx + 6, len(md_lines))):
                if TABLE_CAPTION_RE.match(md_lines[j]):
                    is_table = True
                    break

        if duplicate_of:
            kind = "duplicate"
        elif line_idx is None:
            kind = "orphan"          # file on disk, never referenced in the MD
        elif is_table:
            kind = "table"
        elif not caption and (bulk_noise or f.name in repeated or first_page):
            # A caption-less image on the first page is the publisher logo or
            # the journal header, which every converter segments as a figure.
            kind = "noise"
        else:
            kind = "figure"

        rel = None
        if page is not None:
            rel = os.path.relpath(f, page.parent)

        out["figures"].append({
            "file": f.name,
            "path": str(f.relative_to(REPO_ROOT)),
            "rel_from_page": rel,
            "kind": kind,
            "label": label,
            "caption": caption,
            "printed_page": printed_page,
            "pdf_page": pdf_page,
            "duplicate_of": duplicate_of,
            "bytes": f.stat().st_size,
            "_line": line_idx if line_idx is not None else 10**9,
        })
    # Reading order, not file-name order: 'img-10' sorts before 'img-2'.
    out["figures"].sort(key=lambda r: (r["_line"], r["file"]))
    for r in out["figures"]:
        r.pop("_line", None)

    # Second pass: a PDF page becomes a PRINTED page only once the
    # article's page range is known, and the range is only trustworthy
    # when it covers every page the figures claim.
    max_pdf = max([f["pdf_page"] for f in out["figures"] if f["pdf_page"]] or [0])
    first_printed, mode = printed_page_offset(fm_page or {}, max_pdf) if max_pdf else (None, None)
    out["printed_page_offset"] = first_printed
    out["pagination"] = mode
    if first_printed is not None:
        for f in out["figures"]:
            if f["printed_page"] is None and f["pdf_page"] is not None:
                f["printed_page"] = first_printed + f["pdf_page"] - 1
    return out


def page_ref(fig: dict) -> str:
    """The page reference to print, never inventing a number.

    A printed page recovered from the article's own anchors is a real
    `(p. N)`. A page index recovered from a marker file name is the PDF
    page, which is not the printed page for a supplement or an offprint,
    so it is labelled as such. Otherwise `(p. ?)`, which the citation
    rule allows and a later pass can resolve.
    """
    if fig["printed_page"] is not None:
        return f"(p. {fig['printed_page']})"
    if fig["pdf_page"] is not None:
        return f"(PDF p. {fig['pdf_page']} - confirm the printed page)"
    return "(p. ?)"


def short_title(caption: str, limit: int = 70) -> str:
    """First sentence of the caption, cut on a word boundary."""
    head = caption.split(". ")[0].strip().rstrip(".")
    if len(head) <= limit:
        return head
    return head[:limit].rsplit(" ", 1)[0] + "..."


def to_markdown(data: dict, include_noise: bool = False) -> str:
    keep = [f for f in data["figures"]
            if f["kind"] == "figure" or (include_noise and f["kind"] != "duplicate")]
    if not keep:
        return ""
    lines = ["## Figures", ""]
    for f in keep:
        cap = dedash(f["caption"]) if f["caption"] else ""
        title = short_title(cap) if cap else "caption not recovered"
        lines.append(f"### {f['label']} - {title} {page_ref(f)}")
        lines.append(f"![{f['label']}]({f['rel_from_page'] or f['path']})")
        lines.append(f"*{cap}*" if cap else "*(caption not recovered in the conversion)*")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", required=True, help="slug of the source")
    ap.add_argument("--raw", help="converted article MD (default: source_file frontmatter)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--markdown", action="store_true", help="emit a ready-to-paste ## Figures section")
    ap.add_argument("--include-noise", action="store_true", help="keep page furniture and tables in the markdown")
    ap.add_argument("--no-pdf", action="store_true", help="do not open the PDF to locate captions (faster, more unknown pages)")
    args = ap.parse_args()

    slug = args.source.strip().removesuffix(".md")
    data = collect(slug, args.raw, use_pdf=not args.no_pdf)
    usable = [f for f in data["figures"] if f["kind"] == "figure"]

    if args.markdown:
        md = to_markdown(data, args.include_noise)
        print(md if md else "# nothing to illustrate", end="\n" if md else "\n")
        return 0 if usable else 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0 if usable else 1

    print(f"figure_pairs: {slug}")
    print(f"  source page : {data['source_page'] or 'NOT FOUND'}"
          f"{'  (already has ## Figures)' if data['has_figures_section'] else ''}")
    print(f"  article     : {data['article'] or 'NOT FOUND'}")
    print(f"  images dir  : {data['images_dir'] or 'none - nothing to illustrate'}")
    print(f"  page anchors: {'found' if data['page_map'] else 'absent'}")
    print(f"  pdf text    : {'read (' + str(data['pdf']) + ')' if data.get('pdf_text') else 'unavailable'}")
    print(f"  printed page: offset {data.get('printed_page_offset') or 'unknown'}"
          f"{' (' + data['pagination'] + ')' if data.get('pagination') else ''}")
    print()
    if not data["figures"]:
        print("  no images.")
        return 1
    counts = {}
    for f in data["figures"]:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    for f in data["figures"]:
        if f["kind"] != "figure":
            continue
        cap = (f["caption"][:90] + "...") if len(f["caption"]) > 90 else f["caption"]
        print(f"  {f['label']:<24} {page_ref(f):<40} {f['file']}")
        print(f"    {cap or '(caption not recovered)'}")
    print()
    print("  " + " | ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 0 if usable else 1


if __name__ == "__main__":
    sys.exit(main())
