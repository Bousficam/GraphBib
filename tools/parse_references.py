#!/usr/bin/env python3
"""Parse references from a markdown source's References / Bibliography section.

Three phases, each opt-in via a flag:

    Phase 1 - Extract       (offline, regex)         default
    Phase 2 - Validate      (Crossref agency check)  --validate
    Phase 3 - Curate broken (Crossref free-text)     --curate

Modes:

    python tools/parse_references.py raw/papers/foo.md
        # Phase 1 only. Prints DOIs found by regex. Read-only.

    python tools/parse_references.py --all wiki/sources/
        # Phase 1 only. Walks the directory and writes cites: in each
        # frontmatter (raw regex output, fast, offline).

    python tools/parse_references.py --validate --all wiki/sources/
        # Phase 1 + 2. Each extracted DOI is checked against Crossref.
        # Invalid DOIs are dropped from cites: and the entry is logged
        # in cites_unresolved.

    python tools/parse_references.py --curate --all wiki/sources/
        # Phase 1 + 2 + 3. Invalid or missing DOIs trigger a Crossref
        # free-text search of the reference entry. Recovered DOIs are
        # added to cites: and tagged in cites_curated.

Cache:
    tools/.cache/doi_validation.json - DOIs validated once never re-checked.
    Delete this file to force re-validation.

Frontmatter fields written (only if non-empty):
    cites:             [DOI, ...]    all validated DOIs (regex + curated)
    cites_curated:     [DOI, ...]    subset that came from curation (audit trail)
    cites_unresolved:  [text, ...]   reference entries with no resolvable DOI
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from crossref import (  # noqa: E402
    crossref_search,
    crossref_validate,
    load_cache,
    save_cache,
    title_overlap,
)

REPO_ROOT = Path(__file__).parent.parent
CACHE_DIR = REPO_ROOT / "tools" / ".cache"
# Legacy cache file kept for migration - the new shared cache is
# tools/.cache/crossref.json (managed by tools/crossref.py).
CACHE_FILE = CACHE_DIR / "doi_validation.json"

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
REF_HEADERS = (
    "references",
    "bibliography",
    "cited works",
    "works cited",
    "literature cited",
    "réferences",
    "références",
)
ENTRY_START_RE = re.compile(r"^\s*(?:\[\d+\]|\d{1,3}\.|\(\d{1,3}\))\s+")

USER_AGENT = "graphbib/0.1 (mailto:contact@example.com)"
SLEEP_BETWEEN = 0.05  # 20 req/s, polite for Crossref
MIN_SCORE = 50.0       # Crossref relevance score threshold
MIN_TITLE_OVERLAP = 0.5
MIN_ENTRY_LEN = 30     # too short to curate reliably


# ---------- frontmatter / parsing -------------------------------------------

def parse_fm(text):
    """Split a page into (frontmatter dict, body).

    A file that opens with a `---` block but whose YAML does not parse is an
    error, not a file without frontmatter: returning ({}, text) there would
    make the caller write a fresh frontmatter block ON TOP of the original,
    leaving the page with two `---` blocks and dropping every existing field
    from the new one. Raise instead - the caller reports the file and skips
    it, leaving the page untouched.
    """
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]
            except Exception as e:
                raise ValueError(
                    f"unparseable YAML frontmatter, file left untouched: {e}"
                ) from e
    return {}, text


def extract_references_block(body):
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith("#"):
            continue
        heading = s.lstrip("#").strip().lower().rstrip(":.")
        if any(heading == h or heading.startswith(h + " ") for h in REF_HEADERS):
            return "\n".join(lines[i + 1 :])
    return ""


def extract_dois(text):
    seen, out = set(), []
    for m in DOI_RE.finditer(text):
        d = m.group(0).rstrip(".,;)").lower()
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def split_references(refs_text):
    """Split a references block into individual reference entries.

    Tries three strategies in order:
      1. Lines starting with [N] / N. / (N) - IEEE / numbered / Vancouver.
      2. Blank lines as separators.
      3. Fallback: return whole block as one entry.
    """
    lines = refs_text.splitlines()
    entries, current = [], []
    has_marker = any(ENTRY_START_RE.match(ln) for ln in lines)

    if has_marker:
        for ln in lines:
            if ENTRY_START_RE.match(ln) and current:
                entries.append(" ".join(s.strip() for s in current if s.strip()))
                current = [ln]
            elif ln.strip():
                current.append(ln)
        if current:
            entries.append(" ".join(s.strip() for s in current if s.strip()))
    else:
        chunks = re.split(r"\n\s*\n", refs_text)
        entries = [" ".join(c.split()) for c in chunks if len(c.strip()) >= MIN_ENTRY_LEN]
        if len(entries) <= 1:
            # Single block - leave as-is
            entries = [" ".join(refs_text.split())] if refs_text.strip() else []

    return [e for e in entries if len(e) >= MIN_ENTRY_LEN]


# ---------- cache + Crossref API (moved to tools/crossref.py) ----------------
#
# Cache is shared across all GraphBib tools via `tools/.cache/crossref.json`
# (managed by `tools/crossref.py`). The legacy `doi_validation.json` file
# is no longer read or written - re-runs after this refactor pay one
# Crossref hit per DOI to repopulate the new cache, then are free
# forever.
#
# `crossref_validate`, `crossref_search`, `load_cache`, `save_cache`,
# and `title_overlap` are imported from `crossref` at the top of this
# file.


# ---------- per-source pipeline ---------------------------------------------

def process_source(md_path, do_validate=False, do_curate=False, cache=None):
    if cache is None:
        cache = {}
    text = md_path.read_text(encoding="utf-8")
    fm, body = parse_fm(text)
    refs_text = extract_references_block(body)

    own_doi = (fm.get("doi") or "").strip().lower()
    seen = {own_doi} if own_doi else set()

    cites_valid, cites_curated, unresolved = [], [], []

    if not refs_text:
        return {
            "regex_valid": [],
            "curated": [],
            "unresolved": [],
            "n_entries": 0,
        }

    entries = split_references(refs_text)

    for entry in entries:
        chosen = None
        for d in extract_dois(entry):
            if d in seen:
                continue
            if do_validate:
                if crossref_validate(d, cache):
                    chosen = d
                    break
                # invalid: keep looking in this entry
            else:
                chosen = d
                break

        if chosen:
            cites_valid.append(chosen)
            seen.add(chosen)
            continue

        # No valid DOI from regex. Curate if enabled.
        if do_curate and len(entry) >= MIN_ENTRY_LEN:
            doi = crossref_search(entry)
            if doi and doi not in seen:
                cites_curated.append(doi)
                seen.add(doi)
                continue

        unresolved.append(entry[:200])

    # Write back frontmatter
    new_fm = dict(fm)
    all_cites = cites_valid + cites_curated
    if all_cites:
        new_fm["cites"] = all_cites
    elif "cites" in new_fm:
        del new_fm["cites"]
    if cites_curated:
        new_fm["cites_curated"] = cites_curated
    elif "cites_curated" in new_fm:
        del new_fm["cites_curated"]
    if unresolved:
        new_fm["cites_unresolved"] = unresolved
    elif "cites_unresolved" in new_fm:
        del new_fm["cites_unresolved"]

    fm_text = yaml.safe_dump(new_fm, allow_unicode=True, sort_keys=False).strip()
    md_path.write_text(f"---\n{fm_text}\n---\n\n{body.lstrip()}", encoding="utf-8")

    return {
        "regex_valid": cites_valid,
        "curated": cites_curated,
        "unresolved": unresolved,
        "n_entries": len(entries),
    }


# ---------- importable helper -----------------------------------------------

def extract_dois_from_md(md_path):
    """Phase-1-only convenience function (offline, regex)."""
    text = md_path.read_text(encoding="utf-8")
    _, body = parse_fm(text)
    refs = extract_references_block(body)
    return extract_dois(refs)


# ---------- CLI -------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path", help="Markdown file (or directory with --all)")
    ap.add_argument("--all", action="store_true", help="Recurse into <path> as a directory")
    ap.add_argument("--validate", action="store_true", help="Phase 2: validate DOIs via Crossref")
    ap.add_argument("--curate", action="store_true", help="Phase 3: recover broken/missing DOIs via Crossref free-text (implies --validate)")
    args = ap.parse_args()

    do_validate = args.validate or args.curate
    do_curate = args.curate
    cache = load_cache() if do_validate else {}

    p = Path(args.path).expanduser().resolve()
    if args.all:
        if not p.is_dir():
            sys.exit(f"--all requires a directory: {p}")
        mds = sorted(p.rglob("*.md"))
    else:
        if p.is_dir():
            sys.exit(f"Path is a directory; pass --all to recurse: {p}")
        mds = [p]

    print(
        f"{len(mds)} markdown file(s) - "
        f"validate={do_validate} curate={do_curate}",
        file=sys.stderr,
    )

    summary = {"valid": 0, "curated": 0, "unresolved": 0, "files": 0}
    for i, md in enumerate(mds, 1):
        try:
            stats = process_source(
                md, do_validate=do_validate, do_curate=do_curate, cache=cache
            )
        except Exception as e:
            print(f"  ✗ [{i}/{len(mds)}] {md.name}: {e!r}", file=sys.stderr)
            continue
        summary["valid"] += len(stats["regex_valid"])
        summary["curated"] += len(stats["curated"])
        summary["unresolved"] += len(stats["unresolved"])
        summary["files"] += 1

        if not args.all:
            # Single-file mode: also print DOIs to stdout for piping
            for d in stats["regex_valid"]:
                print(d)
            for d in stats["curated"]:
                print(f"{d}  # curated")
        else:
            tag = "✓"
            if stats["unresolved"] and not stats["regex_valid"] and not stats["curated"]:
                tag = "⚠"
            print(
                f"  {tag} [{i}/{len(mds)}] {md.name}: "
                f"{len(stats['regex_valid'])} valid, "
                f"{len(stats['curated'])} curated, "
                f"{len(stats['unresolved'])} unresolved",
                file=sys.stderr,
            )

        # Periodic cache flush during long runs
        if do_validate and i % 50 == 0:
            save_cache(cache)

    if do_validate:
        save_cache(cache)

    print(
        f"=== {summary['files']} files | {summary['valid']} valid | "
        f"{summary['curated']} curated | {summary['unresolved']} unresolved ===",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
