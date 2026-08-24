#!/usr/bin/env python3
"""Last ingest lint - is this page's DOI the DOI of THIS paper?

A DOI that resolves is not the same as a DOI that is correct. The failure
this catches is silent and common: `enrich_frontmatter.py` reads a DOI
off the converted PDF, and the first DOI printed on a paper is sometimes
one of ITS references, or the journal's own registration. The page then
carries a valid Crossref DOI pointing at somebody else's article, and
every APA citation generated from it is wrong.

So the check is not "does it resolve" but "does what Crossref returns
match the page": title, first author, year, journal.

Checks:

    doi_missing          no doi: on a page type that should have one
    doi_malformed        not a 10.xxxx/... DOI
    doi_not_found        the DOI resolves nowhere (404 at Crossref AND at doi.org)
    doi_not_in_crossref  registered outside Crossref (DataCite: OpenNeuro,
                         Zenodo, figshare) - real DOI, just not cross-checkable
                         here
    doi_title_mismatch   Crossref title is a different paper
    doi_author_mismatch  first author does not match
    doi_year_mismatch    year differs by more than one
    doi_journal_mismatch container title differs
    doi_duplicate        another source page already carries this DOI
    slug_family_mismatch slug does not start with the Crossref author-year

Usage:
    python tools/verify_doi.py --source <slug>
    python tools/verify_doi.py --source <slug> --json
    python tools/verify_doi.py --all              # sweep the vault

Exit code: 0 when no finding reaches `--fail-on` (default `high`), 1
otherwise. Offline is never a failure: an unreachable Crossref is
reported as `crossref_unreachable` (low) and the ingest is not blocked.

When the DOI is missing, a Crossref bibliographic search on the page's
title and first author proposes a candidate. A candidate is a proposal,
never an answer: confirm it against the article before writing it into
the frontmatter, per the Citation Rule (bibliographic frontmatter is
copied verbatim from the source, never invented).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, SRC_DIR, parse_fm  # noqa: E402
from crossref import (  # noqa: E402
    TIMEOUT,
    USER_AGENT,
    crossref_metadata,
    crossref_search,
    load_cache,
    normalize_doi,
    norm_title,
    save_cache,
    slugify,
    title_overlap,
    title_similarity,
)

# A thesis, a book or a lab note legitimately has no DOI; a journal
# article without one is a gap worth reporting.
NO_DOI_EXPECTED = {"thesis", "thesis-chapter", "book", "book-chapter", "notes", "preprint"}

MIN_TITLE_MATCH = 0.75      # SequenceMatcher ratio, page title vs Crossref
MIN_JOURNAL_MATCH = 0.5     # token-Jaccard, container title
YEAR_TOLERANCE = 1          # online-first vs issue year

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def registered_elsewhere(doi: str) -> bool:
    """Does doi.org know this DOI even though Crossref does not?

    Crossref only holds Crossref-registered DOIs. A dataset DOI
    (OpenNeuro, Zenodo, figshare) is registered with DataCite and 404s at
    the Crossref API while being perfectly valid. Without this second
    look, the lint would fail an ingest over a correct DOI.

    A resolvable DOI answers the doi.org proxy with a redirect to the
    publisher. Any network trouble answers False, which only means the
    finding stays where it was - never a new one.
    """
    try:
        import requests
        r = requests.head(
            f"https://doi.org/{doi}",
            timeout=TIMEOUT,
            allow_redirects=False,
            headers={"User-Agent": USER_AGENT},
        )
        return r.status_code in (301, 302, 303, 307, 308)
    except Exception:
        return False


def page_type(fm: dict) -> str:
    """The page's own idea of what it is, for the no-DOI-expected rule."""
    sd = str(fm.get("study_design") or "").strip().lower()
    tags = [str(t).strip().lower() for t in (fm.get("tags") or [])]
    for cand in [sd] + tags:
        if cand in NO_DOI_EXPECTED:
            return cand
    return sd or "article"


def first_author_family(fm: dict) -> str:
    """Surname of the first author, from 'Given Family' or 'Family, Given'."""
    authors = fm.get("authors") or fm.get("editors") or []
    if isinstance(authors, str):
        authors = [authors]
    if not authors:
        return ""
    a = str(authors[0]).strip()
    if "," in a:
        return a.split(",")[0].strip()
    parts = a.split()
    return parts[-1] if parts else ""


def doi_index() -> dict:
    """doi -> [pages carrying it], for duplicate detection. Built once."""
    out = {}
    for p in sorted(SRC_DIR.rglob("*.md")):
        if p.name in {"index.md", "log.md", "overview.md"}:
            continue
        try:
            fm, _ = parse_fm(p.read_text(encoding="utf-8"))
        except OSError:
            continue
        d = str((fm or {}).get("doi") or "").strip().lower()
        if d:
            out.setdefault(d, []).append(p)
    return out


def check_source(path: Path, cache: dict, dupes: dict, offline_hint: dict) -> list:
    fm, _ = parse_fm(path.read_text(encoding="utf-8"))
    fm = fm or {}
    slug = path.stem
    findings = []

    def add(check, severity, detail, **extra):
        rec = {"check": check, "severity": severity, "detail": detail}
        rec.update(extra)
        findings.append(rec)

    raw_doi = str(fm.get("doi") or "").strip()
    ptype = page_type(fm)
    title = str(fm.get("title") or "").strip()
    family = first_author_family(fm)

    if not raw_doi:
        sev = "low" if ptype in NO_DOI_EXPECTED else "medium"
        detail = f"no doi: in the frontmatter (page type: {ptype})"
        candidate = None
        if title:
            query = f"{title} {family}".strip()
            try:
                candidate = crossref_search(query, cache=cache)
            except Exception:
                candidate = None
        if candidate:
            md = crossref_metadata(candidate, cache=cache) or {}
            detail += (
                f"; Crossref proposes {candidate} "
                f"({md.get('first_author', '?')} {md.get('year', '?')}, "
                f"{md.get('title', '?')[:70]}) - confirm against the article "
                f"before writing it"
            )
        add("doi_missing", sev, detail, doi_candidate=candidate)
        return findings

    doi = normalize_doi(raw_doi)
    if not doi:
        add("doi_malformed", "high", f"{raw_doi!r} is not a 10.xxxx/... DOI")
        return findings

    others = [q for q in dupes.get(doi, []) if q != path]
    if others:
        where = ", ".join(str(q.relative_to(REPO_ROOT)) for q in others)
        add("doi_duplicate", "high",
            f"{doi} is already on {where} - same paper ingested twice?")

    try:
        md = crossref_metadata(doi, cache=cache)
    except Exception:
        md = None
        offline_hint["failed"] = True

    if md is None:
        if offline_hint.get("failed"):
            add("crossref_unreachable", "low",
                f"could not reach Crossref for {doi} - re-run when online")
        elif registered_elsewhere(doi):
            add("doi_not_in_crossref", "low",
                f"{doi} is registered outside Crossref (DataCite - a dataset, "
                f"preprint or software DOI). It resolves, so it is not wrong; "
                f"it just cannot be cross-checked against a bibliographic "
                f"record here. Verify the metadata against the landing page.")
        else:
            add("doi_not_found", "high",
                f"{doi} resolves nowhere - not at Crossref, not at doi.org")
        return findings

    cr_title = md.get("title") or ""
    cr_family = md.get("first_author") or ""
    cr_year = str(md.get("year") or "")
    cr_journal = md.get("journal") or ""

    if title and cr_title:
        sim = title_similarity(title, cr_title)
        if sim < MIN_TITLE_MATCH:
            add("doi_title_mismatch", "high",
                f"this DOI is a different paper (similarity {sim:.2f}): "
                f"Crossref says {cr_title!r}",
                crossref_title=cr_title)

    if family and cr_family:
        if norm_title(family) != norm_title(cr_family):
            add("doi_author_mismatch", "medium",
                f"first author {family!r} vs Crossref {cr_family!r}")

    page_year = str(fm.get("year") or "").strip()[:4]
    if page_year.isdigit() and cr_year.isdigit():
        if abs(int(page_year) - int(cr_year)) > YEAR_TOLERANCE:
            add("doi_year_mismatch", "medium",
                f"year {page_year} vs Crossref {cr_year}")

    page_journal = str(fm.get("journal") or fm.get("container_title") or "").strip()
    if page_journal and cr_journal:
        if title_overlap(page_journal, cr_journal) < MIN_JOURNAL_MATCH:
            add("doi_journal_mismatch", "low",
                f"journal {page_journal!r} vs Crossref {cr_journal!r}")

    if cr_family and cr_year:
        expected = f"{slugify(cr_family)}-{cr_year}"
        if not slug.startswith(slugify(cr_family)):
            add("slug_family_mismatch", "low",
                f"slug {slug!r} does not start with the Crossref author "
                f"({expected})")

    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", help="slug of the just-ingested source")
    ap.add_argument("--all", action="store_true", help="sweep every source page in the vault")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--fail-on", choices=["low", "medium", "high"], default="high")
    ap.add_argument("--warn-only", action="store_true", help="always exit 0")
    args = ap.parse_args()

    if not args.source and not args.all:
        ap.error("pass --source <slug> or --all")

    if args.all:
        pages = [p for p in sorted(SRC_DIR.rglob("*.md"))
                 if p.name not in {"index.md", "log.md", "overview.md"}]
    else:
        slug = args.source.strip().removesuffix(".md")
        pages = sorted(SRC_DIR.rglob(f"{slug}.md"))
        if not pages:
            sys.exit(f"no source page found for slug {slug!r} under {SRC_DIR}")
        pages = pages[:1]

    cache = load_cache()
    offline_hint = {}
    dupes = doi_index()
    results = []
    for p in pages:
        findings = check_source(p, cache, dupes, offline_hint)
        if findings:
            results.append({"file": str(p.relative_to(REPO_ROOT)),
                            "slug": p.stem,
                            "checks": findings})
    save_cache(cache)

    counts = {"low": 0, "medium": 0, "high": 0}
    for r in results:
        for c in r["checks"]:
            counts[c["severity"]] += 1

    if args.json:
        print(json.dumps({"pages_checked": len(pages), "counts": counts,
                          "findings": results}, indent=2, ensure_ascii=False))
    else:
        print(f"verify_doi: {len(pages)} page(s) checked")
        print()
        if not results:
            print("  OK - DOI resolves at Crossref and matches the page.")
        for r in results:
            print(f"  {r['file']}")
            for c in r["checks"]:
                print(f"    [{c['severity']}] {c['check']}: {c['detail']}")
            print()
        print(f"  high {counts['high']} | medium {counts['medium']} | low {counts['low']}")

    if args.warn_only:
        return 0
    threshold = SEVERITY_ORDER[args.fail_on]
    hit = any(SEVERITY_ORDER[c["severity"]] >= threshold
              for r in results for c in r["checks"])
    return 1 if hit else 0


if __name__ == "__main__":
    sys.exit(main())
