#!/usr/bin/env python3
"""Minimal post-ingest lint - are the results written during an ingest real?

Answers one question per numeric claim produced by an ingest:

    1. cited      - does the claim carry a page reference (and, on a page
                    other than the source page itself, a [[wikilink]] to
                    the source it comes from)?
    2. referenced - does that wikilink resolve to a page that exists?
    3. present    - does every number in the claim actually appear in the
                    ingested article (the raw converted markdown)?

Check 3 is the important one: it catches numbers that were paraphrased,
mis-OCR'd, transposed from the wrong row of a table, or invented.

Scope. By default the tool checks the source page for <slug> plus every
wiki page that wikilinks to [[<slug>]] - i.e. exactly the pages an ingest
touches. On those other pages only the lines that cite [[<slug>]] are
checked, so a page carrying claims from ten sources is not re-audited in
full on every ingest.

Usage:
    python tools/verify_ingest.py --source <slug>
    python tools/verify_ingest.py --source <slug> --raw path/to/article.md
    python tools/verify_ingest.py --source <slug> --pages wiki/concepts/A.md
    python tools/verify_ingest.py --source <slug> --json
    python tools/verify_ingest.py --source <slug> --check-page-refs

Exit code: 0 when no finding above the `--fail-on` severity (default
`high`), 1 otherwise. `--warn-only` always exits 0.

Findings are candidates, not verdicts: the agent re-reads the flagged
line against the article, then fixes the claim or the citation. A number
reported as absent can also be a conversion artefact (a table the OCR
shredded); in that case the fix is to say so on the page, not to keep a
number nobody can check.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, SRC_DIR, WIKI_DIR, parse_fm  # noqa: E402

# Sections whose lines are bookkeeping, not claims about the article.
SKIP_SECTIONS = {
    "cites",
    "cites (in-wiki + snowball candidates)",
    "cited by",
    "connections",
    "contradictions",
    "extraction checklist",
    "how to cite",
    "references",
    "bibliography",
    "notable references",
    "notable references (citation snowball)",
    "figures",
    "sources in this wiki",
}

# Everything masked here is layout or citation machinery, never a result.
MASKS = [
    re.compile(r"`[^`]*`"),                                  # inline code
    re.compile(r"!\[[^\]]*\]\([^)]*\)"),                     # images
    re.compile(r"\[[^\]]*\]\([^)]*\)"),                      # md links
    re.compile(r"\[\[[^\]]*\]\]"),                           # wikilinks
    re.compile(r"\bpp?\.\s*[A-Za-z]?[0-9?]+(?:\s*-\s*[A-Za-z]?[0-9]+)?", re.I),  # p. 12, pp. 12-15, p. S81
    re.compile(
        r"\b(?:figs?|figures?|tabs?|tables?|eq|equation|sec|section|appendix|chap|chapter|box)\.?"
        r"\s*[0-9]+[A-Za-z]?(?:\.[0-9]+)*(?:\s*[-,]\s*[0-9]+[A-Za-z]?)*",
        re.I,
    ),
    re.compile(r"\brefs?\.?\s*[0-9]+(?:\s*[-,]\s*[0-9]+)*", re.I),  # refs 42-48
    re.compile(r"\[[0-9,\s-]+\]"),                           # [43, 44]
    re.compile(r"\b[0-9]{4}-[0-9]{2}-[0-9]{2}\b"),           # ISO dates
    re.compile(r"\bCRD[0-9]+\b", re.I),                      # registry ids
    re.compile(r"\b10\.[0-9]{4,9}/\S+"),                     # DOIs
]

# The lookbehind keeps a hyphen range ('1-10', '[0.02-0.40]') from being read
# as a negative number, stops '0.14' from also yielding '14', and skips digits
# glued to a word ('P300', 'COVID19') - those are names, not results. Spaces
# and thousand separators inside a number are already gone (see normalize()).
NUM_RE = re.compile(r"(?<![\d.A-Za-z])[-+]?\d+(?:\.\d+)?%?")
# Accepts 'p. 12', 'pp. 12-15', supplement pages ('p. S81', 'p. e204'),
# roman front matter ('p. iv') and the deliberate unknown '(intro p. ?)'.
PAGE_REF_RE = re.compile(r"\bpp?\.\s*(?:[A-Za-z]?[0-9]+|[ivxlcIVXLC]+|\?)", re.I)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

# Running-header page markers left by the conversion backends. Only used
# with --check-page-refs, and only when they cover enough of the file to
# be trustworthy.
PAGE_MARKERS = [
    re.compile(r"^\s*Page\s+(\d+)\s+of\s+\d+\s*$", re.I),
    re.compile(r"^\s*<!--\s*page\s*[:=]?\s*(\d+)\s*-->\s*$", re.I),
    re.compile(r"^\s*\[?page\s+(\d+)\]?\s*$", re.I),
    re.compile(r"^\s*-{2,}\s*page\s+(\d+)\s*-{2,}\s*$", re.I),
]

YEAR_RE = re.compile(r"(?:1[5-9]|20)[0-9]{2}")

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


# ---------- normalisation ---------------------------------------------------

def normalize(text: str) -> str:
    """Fold the spelling differences that make the same number look different.

    Unicode minus / dashes -> '-', non-breaking and thin spaces -> ' ',
    thousand separators and spaces inside numbers dropped ('1 630' and
    '1,630' both become '1630'), and the space before '%' removed. Applied
    to BOTH the article and the claim so the comparison is symmetric.
    """
    # Dashes written as escapes: the house style bans literal em / en dashes
    # in source, and these must MATCH what the raw corpus prints.
    for dash in ("\u2212", "\u2013", "\u2014"):   # minus, en dash, em dash
        text = text.replace(dash, "-")
    t = text
    for sp in ("\u00a0", "\u2009", "\u202f"):  # nbsp, thin, narrow nbsp
        t = t.replace(sp, " ")
    t = re.sub(r"(?<=\d)[ ,](?=\d)", "", t)   # 1 630 / 1,630 -> 1630
    t = re.sub(r"(\d)\s+%", r"\1%", t)
    return t


ORDERED_MARKER_RE = re.compile(r"^(\s*)(\d+)([.)]\s)")


def mask(line: str) -> str:
    """Blank out layout / citation machinery so it is not read as a result."""
    # An ordered-list marker ("21. Protect neural-data privacy") is not a claim.
    out = ORDERED_MARKER_RE.sub(lambda m: m.group(1) + " " * len(m.group(2)) + m.group(3), line)
    for rx in MASKS:
        out = rx.sub(lambda m: " " * len(m.group(0)), out)
    return out


def numeric_tokens(line: str) -> list[str]:
    """Numbers a claim asserts, after masking. Deduplicated, order kept."""
    seen, out = set(), []
    for m in NUM_RE.finditer(normalize(mask(line))):
        tok = m.group(0).strip().rstrip(".,;:")
        tok = re.sub(r"\s+", "", tok)
        if not tok or not re.search(r"\d", tok):
            continue
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def token_body(token: str) -> str:
    """The number itself: no percent sign, no cosmetic leading plus."""
    return token.rstrip("%").lstrip("+")


def token_present(token: str, haystack: str) -> bool:
    """Is `token` in the article as a standalone number?

    Boundaries stop '14' from matching inside '0.145' or '2014', while
    still allowing the article to write '0.14)' or 'n=54,'.
    """
    pat = re.compile(r"(?<![\d.])" + re.escape(token_body(token)) + r"(?![\d])")
    return bool(pat.search(haystack))


def article_values(raw_norm: str) -> set:
    """Every number the article prints, as floats.

    Used as the second chance for a claim whose number is not found
    verbatim: '0.050' vs '0.05', '+5.0' vs '5.0' are the same measurement
    written differently, which is a formatting note, not a missing value.
    """
    out = set()
    for tok in NUM_RE.findall(raw_norm):
        try:
            out.add(float(token_body(tok)))
        except ValueError:
            continue
    return out


# ---------- page map (opt-in) -----------------------------------------------

def build_page_map(raw_text: str):
    """line index -> printed page number, from running-header markers.

    Returns None when no marker family covers the file densely enough
    (< 1 marker per 200 lines): a sparse map produces bogus mismatches.
    """
    lines = raw_text.splitlines()
    best = None
    for rx in PAGE_MARKERS:
        hits = [(i, int(m.group(1))) for i, ln in enumerate(lines) if (m := rx.match(ln))]
        if len(hits) > (len(best) if best else 0):
            best = hits
    if not best or len(best) < max(3, len(lines) // 200):
        return None
    page_of = {}
    current = best[0][1]
    idx = 0
    for i in range(len(lines)):
        while idx < len(best) and best[idx][0] <= i:
            current = best[idx][1]
            idx += 1
        page_of[i] = current
    return page_of


def pages_for_token(token: str, raw_lines: list[str], page_map) -> list[int]:
    body = token.rstrip("%")
    pat = re.compile(r"(?<![\d.])" + re.escape(body) + r"(?![\d])")
    pages = []
    for i, ln in enumerate(raw_lines):
        if pat.search(normalize(ln)):
            p = page_map.get(i)
            if p is not None and p not in pages:
                pages.append(p)
    return pages


# ---------- page walking ----------------------------------------------------

def claim_lines(text: str):
    """Yield (line_no, line, has_context_ref) for lines that can carry a claim.

    Skips frontmatter, headings, code fences, blank lines, and the
    bookkeeping sections listed in SKIP_SECTIONS.

    `has_context_ref` says whether a page reference covers the line from
    its surroundings rather than from the line itself: a `(p. N)` in the
    current heading, or - for a table row - in the sentence introducing
    the table. Wiki pages routinely anchor a whole table once above it,
    so without this every row of a verbatim table reads as uncited.
    """
    _, body = parse_fm(text)
    offset = len(text.splitlines()) - len(body.splitlines())
    in_fence = False
    skipping = False
    heading_ref = False
    block_ref = False
    for i, line in enumerate(body.splitlines(), start=offset + 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        h = HEADING_RE.match(stripped)
        if h:
            title = h.group(2).strip().lower().rstrip(":.")
            if len(h.group(1)) <= 2:          # a ## resets the skip state
                skipping = title in SKIP_SECTIONS
            elif title in SKIP_SECTIONS:      # a ### can also open one
                skipping = True
            heading_ref = bool(PAGE_REF_RE.search(stripped))
            block_ref = False
            continue
        if skipping:
            continue
        # A table row or a block quote inherits the reference written on
        # the line that introduces it ("**Results (primary outcome, p. 9)**").
        inherits = stripped.startswith("|") or stripped.startswith(">")
        if stripped.startswith("|") and set(stripped) <= set("|-: "):
            continue                          # table separator row
        if not inherits:
            block_ref = bool(PAGE_REF_RE.search(stripped))
        yield i, line, heading_ref or (inherits and block_ref)


def resolve_source_page(slug: str) -> Path | None:
    hits = sorted(SRC_DIR.rglob(f"{slug}.md"))
    return hits[0] if hits else None


def resolve_raw(fm: dict, slug: str) -> Path | None:
    for key in ("source_file", "source_md"):
        val = (fm.get(key) or "").strip()
        if not val:
            continue
        p = Path(val)
        if not p.is_absolute():
            p = REPO_ROOT / p
        if p.is_file() and p.suffix.lower() == ".md":
            return p
    hits = sorted((REPO_ROOT / "raw").rglob(f"{slug}.md"))
    return hits[0] if hits else None


def linking_pages(slug: str, source_page: Path) -> list[Path]:
    """Wiki pages that wikilink to [[slug]] - what the ingest propagated to."""
    needle = f"[[{slug}"
    out = []
    for p in sorted(WIKI_DIR.rglob("*.md")):
        if p == source_page or p.name in {"index.md", "log.md", "overview.md"}:
            continue
        if p.name.endswith("-report.md") or p.name == "figures-index.md":
            continue
        try:
            if needle in p.read_text(encoding="utf-8"):
                out.append(p)
        except OSError:
            continue
    return out


def page_exists(name: str) -> bool:
    stem = name.strip().split("/")[-1]
    if not stem:
        return False
    return any(WIKI_DIR.rglob(f"{stem}.md"))


# ---------- the check itself ------------------------------------------------

def check_page(path: Path, slug: str, raw_norm: str, art_values: set,
               is_source_page: bool, raw_lines=None, page_map=None) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    findings = []
    for lineno, line, context_ref in claim_lines(text):
        links = WIKILINK_RE.findall(line)
        if not is_source_page and slug not in [l.strip().split("/")[-1] for l in links]:
            continue                          # not this ingest's claim
        tokens = numeric_tokens(line)
        if not tokens:
            continue

        rec = {
            "file": str(path.relative_to(REPO_ROOT)),
            "line": lineno,
            "text": line.strip()[:300],
            "checks": [],
        }

        if not (PAGE_REF_RE.search(line) or context_ref):
            rec["checks"].append({
                "check": "missing_page_ref",
                "severity": "medium",
                "detail": "numeric claim with no (p. N) reference, here or above it",
            })

        if not is_source_page:
            for name in links:
                if not page_exists(name):
                    rec["checks"].append({
                        "check": "broken_citation",
                        "severity": "high",
                        "detail": f"[[{name}]] resolves to no page",
                    })

        absent, reformatted = [], []
        for t in tokens:
            if token_present(t, raw_norm):
                continue
            try:
                val = float(token_body(t))
            except ValueError:
                val = None
            (reformatted if val is not None and val in art_values else absent).append(t)
        if absent:
            rec["checks"].append({
                "check": "not_in_article",
                "severity": "high",
                "detail": "not found in the article: " + ", ".join(absent),
            })
        if reformatted:
            rec["checks"].append({
                "check": "number_reformatted",
                "severity": "low",
                "detail": (
                    "same value, different printing in the article (rounding, "
                    "trailing zero, sign): " + ", ".join(reformatted)
                ),
            })

        if page_map is not None:
            cited = {int(m) for m in re.findall(r"\bpp?\.\s*(\d+)", line, re.I)}
            if cited:
                found = []
                for t in tokens:
                    if t in absent or YEAR_RE.fullmatch(t):
                        continue          # a citation year proves nothing
                    hits = pages_for_token(t, raw_lines, page_map)
                    if 0 < len(hits) <= 3:   # only distinctive numbers locate a page
                        found.extend(hits)
                if found and not (cited & set(found)):
                    rec["checks"].append({
                        "check": "page_ref_mismatch",
                        "severity": "low",
                        "detail": (
                            f"cited p. {sorted(cited)}, numbers found on "
                            f"p. {sorted(set(found))[:6]}"
                        ),
                    })

        if rec["checks"]:
            findings.append(rec)
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", required=True, help="slug of the just-ingested source")
    ap.add_argument("--raw", help="path to the converted article MD (default: source_file frontmatter)")
    ap.add_argument("--pages", nargs="*", help="extra wiki pages to check (default: every page linking to the slug)")
    ap.add_argument("--only-source-page", action="store_true", help="check the source page alone")
    ap.add_argument("--check-page-refs", action="store_true", help="also cross-check (p. N) against the article's page markers")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--fail-on", choices=["low", "medium", "high"], default="high")
    ap.add_argument("--warn-only", action="store_true", help="always exit 0")
    args = ap.parse_args()

    slug = args.source.strip().removesuffix(".md")
    src_page = resolve_source_page(slug)
    if src_page is None:
        sys.exit(f"no source page found for slug {slug!r} under {SRC_DIR}")

    fm, _ = parse_fm(src_page.read_text(encoding="utf-8"))
    raw_path = Path(args.raw).expanduser() if args.raw else resolve_raw(fm, slug)
    if raw_path is None or not raw_path.is_file():
        sys.exit(
            f"no converted article MD for {slug!r} "
            f"(set source_file: in the frontmatter or pass --raw)"
        )

    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    raw_norm = normalize(raw_text)
    art_values = article_values(raw_norm)
    raw_lines = raw_text.splitlines()
    page_map = build_page_map(raw_text) if args.check_page_refs else None

    targets = [(src_page, True)]
    if not args.only_source_page:
        extra = [Path(p) for p in (args.pages or [])] or linking_pages(slug, src_page)
        targets += [((REPO_ROOT / p if not p.is_absolute() else p), False) for p in extra]

    findings = []
    for path, is_src in targets:
        if not path.is_file():
            continue
        findings += check_page(path, slug, raw_norm, art_values, is_src, raw_lines, page_map)

    counts = {"low": 0, "medium": 0, "high": 0}
    for f in findings:
        for c in f["checks"]:
            counts[c["severity"]] += 1

    if args.json:
        print(json.dumps({
            "slug": slug,
            "source_page": str(src_page.relative_to(REPO_ROOT)),
            "article": str(raw_path),
            "pages_checked": len(targets),
            "page_map": page_map is not None,
            "counts": counts,
            "findings": findings,
        }, indent=2, ensure_ascii=False))
    else:
        print(f"verify_ingest: {slug}")
        print(f"  source page : {src_page.relative_to(REPO_ROOT)}")
        print(f"  article     : {raw_path}")
        print(f"  pages       : {len(targets)} checked")
        if args.check_page_refs:
            print(f"  page map    : {'built' if page_map else 'unavailable (no page markers)'}")
        print()
        if not findings:
            print("  OK - every numeric claim is cited and present in the article.")
        for f in findings:
            print(f"  {f['file']}:{f['line']}")
            print(f"    {f['text']}")
            for c in f["checks"]:
                print(f"    [{c['severity']}] {c['check']}: {c['detail']}")
            print()
        print(f"  high {counts['high']} | medium {counts['medium']} | low {counts['low']}")

    if args.warn_only:
        return 0
    threshold = SEVERITY_ORDER[args.fail_on]
    hit = any(
        SEVERITY_ORDER[c["severity"]] >= threshold
        for f in findings for c in f["checks"]
    )
    return 1 if hit else 0


if __name__ == "__main__":
    sys.exit(main())
