#!/usr/bin/env python3
"""Audit + (optionally) rename raw inputs so they match the wiki source slug.

Wiki source pages live at `wiki/<vault>/sources/<...>/<slug>.md`. Their
raw inputs (PDF + converted markdown + extracted-images directory) live
at `raw/<vault>/{papers,theses,books,notes}/<basename>.{pdf,md}` and
`raw/<vault>/.../<basename>_images/`.

For consistency we want every raw triple to be named `<slug>` - same
as the wiki source page. This script audits the wiki, finds mismatches,
classifies each, and (with --apply) renames the unambiguous ones.

Usage:

    python tools/audit_raw.py                  # dry-run audit, table to stdout
    python tools/audit_raw.py --apply          # auto-rename unambiguous cases
    python tools/audit_raw.py --source <slug>  # audit a single source page

Classification:

    ok          basename(source_pdf/source_file) == slug
    rename      basename differs but the file exists → safe to rename
    external    a pointer resolves OUTSIDE the repo (e.g. the master PDF in
                an ownCloud library). Reported, never renamed, never
                rewritten - the on-disk name out there is authoritative.
    missing     frontmatter points to a path that does not exist
    ambiguous   frontmatter is empty AND >1 raw candidate fits the slug
    orphan_raw  raw file present with no matching wiki source

Exit code is the number of unresolved findings (rename + missing +
ambiguous + orphan_raw), so the librarian can react.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (  # noqa: E402
    RAW_DIR,
    REPO_ROOT,
    SRC_DIR,
    load_sources,
    parse_fm,
    raw_subdir,
)

RAW_KINDS = ("papers", "theses", "books", "notes")
IMG_SUFFIX = "_images"

# Frontmatter fields that may carry a raw path.
RAW_FIELDS = ("source_file", "source_pdf")


def _slugify_basename(name: str) -> str:
    """Lowercased, dashed, accent-stripped version of a filename stem."""
    import unicodedata

    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _abs_norm(raw_path: str) -> Path:
    """Absolute, lexically normalized form of a frontmatter raw path.

    Relative values are taken relative to REPO_ROOT. `os.path.normpath`
    collapses any `..` segment, so a value such as
    `../../ownCloud/lib/x.pdf` lands on its real location instead of
    staying a repo-prefixed string that `Path.relative_to` would happily
    accept as "inside the repo".
    """
    p = Path(raw_path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return Path(os.path.normpath(p))


def _inside_repo(raw_path: str) -> bool:
    """True when a frontmatter raw path points inside the repo working tree.

    Anything else (an ownCloud master PDF, a TallyBib copy, any absolute
    path elsewhere on disk) is a file this repo does not own: it must
    never be renamed and its pointer must never be rewritten.
    """
    try:
        _abs_norm(raw_path).relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


def _resolve(raw_path: str) -> Path | None:
    """Resolve a frontmatter raw path to an existing absolute Path or None."""
    if not raw_path or not isinstance(raw_path, str):
        return None
    p = _abs_norm(raw_path)
    return p if p.exists() else None


def _raw_kind_of(path: Path) -> str | None:
    """Return 'papers' | 'theses' | 'books' | 'notes' for a raw path."""
    try:
        parts = path.relative_to(RAW_DIR).parts
    except ValueError:
        return None
    return parts[0] if parts and parts[0] in RAW_KINDS else None


def _candidate_for(slug: str) -> Path | None:
    """If exactly one raw file across kinds has a stem similar to slug, return it."""
    target = _slugify_basename(slug)
    hits: list[Path] = []
    for kind in RAW_KINDS:
        d = raw_subdir(kind)
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".pdf", ".md"):
                continue
            if _slugify_basename(p.stem) == target:
                hits.append(p)
    # de-dup by stem so a (.pdf, .md) pair counts as one slot
    stems = {h.with_suffix("") for h in hits}
    if len(stems) == 1:
        return hits[0]
    return None


def _triple_paths(canon: Path) -> list[Path]:
    """All files / dirs that move together with a raw rename."""
    stem = canon.with_suffix("")
    siblings = [stem.with_suffix(".pdf"), stem.with_suffix(".md")]
    img = canon.parent / f"{canon.stem}{IMG_SUFFIX}"
    return [p for p in siblings if p.exists()] + ([img] if img.is_dir() else [])


def _classify(source: dict) -> dict:
    """Return a finding dict for one wiki source page."""
    slug = source["slug"]
    fm = source["fm"] or {}

    pointers: list[Path] = []
    missing_fields: list[str] = []
    for field in RAW_FIELDS:
        val = fm.get(field)
        if not val:
            continue
        resolved = _resolve(val)
        if resolved is None:
            missing_fields.append(field)
        else:
            pointers.append(resolved)

    # Pointers are split by ownership: only files inside the repo may be
    # renamed. An external pointer (ownCloud master PDF and friends) can
    # never be acted on, so a mismatched basename out there is a fact to
    # report, not a finding to resolve.
    internal = [p for p in pointers if _inside_repo(str(p))]
    external = [p for p in pointers if p not in internal]

    if internal and any(p.stem != slug for p in internal):
        return {
            "status": "rename",
            "slug": slug,
            "canon": internal[0],
            "wiki_path": source["path"],
            "fields": [(f, fm.get(f)) for f in RAW_FIELDS if fm.get(f)],
        }

    # Only a MISMATCHED external pointer is worth reporting: it is the case
    # that used to be filed as `rename`, which invited an --apply that then
    # rewrote the pointer to a filename nobody ever created. An external
    # pointer already named after the slug needs no signal at all.
    external_mismatch = [p for p in external if p.stem != slug]
    if external_mismatch:
        return {
            "status": "external",
            "slug": slug,
            "canon": internal[0] if internal else external[0],
            "external": external_mismatch,
        }

    if internal or external:
        return {"status": "ok", "slug": slug, "canon": (internal or external)[0]}

    cand = _candidate_for(slug)
    if cand is not None:
        return {
            "status": "rename" if cand.stem != slug else "ok",
            "slug": slug,
            "canon": cand,
            "wiki_path": source["path"],
            "fields": [],
        }

    if missing_fields:
        return {"status": "missing", "slug": slug, "fields": missing_fields}
    return {"status": "ambiguous", "slug": slug}


def _orphan_raws(findings: list[dict]) -> list[Path]:
    """Raw files whose stem matches no wiki source slug *and* are not
    already referenced by a `rename` / `ok` finding."""
    known_slugs = {f["slug"] for f in findings}
    referenced: set[Path] = set()
    for f in findings:
        canon = f.get("canon")
        if canon is None:
            continue
        for p in _triple_paths(canon):
            if not p.is_dir():
                referenced.add(p.resolve())
    orphans = []
    for kind in RAW_KINDS:
        d = raw_subdir(kind)
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if not p.is_file() or p.suffix.lower() not in (".pdf", ".md"):
                continue
            if p.resolve() in referenced:
                continue
            if p.stem in known_slugs:
                continue
            if _slugify_basename(p.stem) in {_slugify_basename(s) for s in known_slugs}:
                continue
            orphans.append(p)
    return orphans


def _apply_rename(finding: dict, dry_run: bool) -> list[str]:
    """Rename one source's raw triple to `<slug>.{ext}` and repoint its frontmatter.

    Input: a `rename` finding from `_classify` (keys `slug`, `canon`,
    `wiki_path`, `fields`) and `dry_run`. Output: the list of action
    lines describing what was done or skipped, for the caller to print.

    Side effects when `dry_run` is False: renames files and the
    `<stem>_images/` directory on disk under `raw/`, and rewrites the
    wiki source page in place.

    What is deliberately NEVER touched, in either phase:
      - any path outside the repo working tree. The master PDF usually
        lives in an external library (`~/ownCloud/Biblio PhD/...`) under
        a human-readable name that does not follow the slug convention.
        Renaming it is not ours to do, and rewriting `source_pdf` to
        `<slug>.pdf` invents a filename that never existed, silently
        breaking the pointer.
      - a field whose rename was skipped because the target already
        existed, or whose target does not exist after the rename ran.
    In those cases the on-disk name is authoritative: the mismatch is
    reported as a SKIP line and left for a human to reconcile.
    """
    slug = finding["slug"]
    canon = finding["canon"]
    actions: list[str] = []

    triple = _triple_paths(canon)
    for old in triple:
        if not _inside_repo(str(old)):
            # Pointer resolves outside the repo (e.g. an absolute path into
            # an external library such as an ownCloud master copy). Never
            # rename files we don't own - surface for manual reconciliation.
            actions.append(f"SKIP  {old} (outside repo - external file, not renamed)")
            continue
        if old.is_dir():
            new = old.parent / f"{slug}{IMG_SUFFIX}"
        else:
            new = old.parent / f"{slug}{old.suffix}"
        if old == new:
            continue
        if new.exists():
            actions.append(f"SKIP  {old} → {new} (target exists)")
            continue
        actions.append(f"MV    {old.relative_to(REPO_ROOT)} → {new.relative_to(REPO_ROOT)}")
        if not dry_run:
            old.rename(new)

    # Rewrite wiki source frontmatter so source_file / source_pdf point to new path.
    #
    # A field is only rewritten when the file it points at was actually renamed
    # above. Two cases must be left alone, and both used to be silently
    # rewritten into a dangling pointer:
    #   - the pointer resolves outside the repo (an external master copy, e.g.
    #     an ownCloud PDF). The rename loop skips those by design, so pointing
    #     the frontmatter at "<slug>.pdf" invents a filename that never existed.
    #   - the rename was skipped because the target already existed.
    # In both cases the on-disk name is authoritative and the pointer is correct
    # as written.
    wiki_path = finding.get("wiki_path")
    if wiki_path:
        text = Path(wiki_path).read_text(encoding="utf-8")
        new_text = text
        rewritten = 0
        for field, old_val in finding.get("fields", []):
            if not _inside_repo(old_val):
                actions.append(f"SKIP  frontmatter {field} (points outside repo - left as is)")
                continue
            old_p = Path(old_val)
            new_p = old_p.parent / f"{slug}{old_p.suffix}"
            if new_p == old_p:
                continue
            abs_new = new_p if new_p.is_absolute() else REPO_ROOT / new_p
            # In dry-run the rename has not happened yet, so absence is expected.
            if not dry_run and not abs_new.exists():
                actions.append(f"SKIP  frontmatter {field} (target {new_p} does not exist)")
                continue
            new_text = new_text.replace(old_val, str(new_p), 1)
            rewritten += 1
        if new_text != text:
            actions.append(f"FM    {Path(wiki_path).relative_to(REPO_ROOT)} (updated {rewritten} field(s))")
            if not dry_run:
                Path(wiki_path).write_text(new_text, encoding="utf-8")
    return actions


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="Rename unambiguous cases")
    ap.add_argument("--source", help="Audit only this source slug")
    args = ap.parse_args()

    sources = load_sources()
    if args.source:
        sources = [s for s in sources if s["slug"] == args.source]
        if not sources:
            sys.exit(f"No wiki source named {args.source!r}")

    findings = [_classify(s) for s in sources]
    by_status: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        by_status[f["status"]].append(f)

    orphans = _orphan_raws(findings) if not args.source else []

    # ---- Report ----
    print(f"Wiki sources: {len(sources)} | raw root: {RAW_DIR}")
    print(f"  ok       : {len(by_status['ok'])}")
    print(f"  rename   : {len(by_status['rename'])}")
    print(f"  external : {len(by_status['external'])}")
    print(f"  missing  : {len(by_status['missing'])}")
    print(f"  ambiguous: {len(by_status['ambiguous'])}")
    print(f"  orphans  : {len(orphans)}")
    print()

    if by_status["rename"]:
        print("== rename ==")
        for f in by_status["rename"]:
            try:
                canon_display = f['canon'].relative_to(REPO_ROOT)
            except ValueError:
                # canon pointer resolves outside the repo (e.g. an absolute
                # path into an external library such as an ownCloud master
                # copy) - show it as-is instead of crashing.
                canon_display = f['canon']
            print(f"  {f['slug']:<35}  raw: {canon_display}")
            if args.apply:
                for a in _apply_rename(f, dry_run=False):
                    print(f"     {a}")
            else:
                for a in _apply_rename(f, dry_run=True):
                    print(f"     [dry] {a}")
        print()

    if by_status["external"]:
        print("== external (raw pointer outside the repo - reported, never rewritten) ==")
        for f in by_status["external"]:
            for p in f.get("external", []):
                print(f"  {f['slug']:<35}  {p}")
        print()

    if by_status["missing"]:
        print("== missing (raw paths in frontmatter don't exist) ==")
        for f in by_status["missing"]:
            print(f"  {f['slug']:<35}  fields: {', '.join(f['fields'])}")
        print()

    if by_status["ambiguous"]:
        print("== ambiguous (no usable pointer, multiple or zero candidates) ==")
        for f in by_status["ambiguous"]:
            print(f"  {f['slug']}")
        print()

    if orphans:
        print("== orphan raws (no matching wiki source) ==")
        for o in orphans:
            print(f"  {o.relative_to(REPO_ROOT)}")
        print()

    unresolved = (
        len(by_status["rename"]) * (0 if args.apply else 1)
        + len(by_status["missing"])
        + len(by_status["ambiguous"])
        + len(orphans)
    )
    sys.exit(0 if unresolved == 0 else min(unresolved, 99))


if __name__ == "__main__":
    main()
