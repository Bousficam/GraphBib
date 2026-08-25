#!/usr/bin/env python3
"""File a source's master PDF into the reference library, named by its slug.

Runs at the end of an ingest (step 21), once the DOI has been verified -
the slug is only trustworthy after that, and filing a PDF under a wrong
slug is worse than not filing it.

    <ref-dir>/<theme>/<slug>.pdf

The **theme** is the one the ingest already decided: the folder the wiki
source page sits in under `sources/`. Its last meaningful segment is
matched case-insensitively against the folders already in the library,
so a page in `articles/bci/` lands in an existing `BCI/` rather than
creating a second one. With no match the folder is created under the
wiki's own name, which keeps the repo domain-neutral - no hard-coded
vocabulary here.

This does NOT replace `raw/`. `raw/<vault>/papers/` keeps the converted
markdown and the extracted images - the corpus the wiki was built from,
immutable. The reference library keeps the PDFs a human opens. Both
pointers live on the source page: `source_file` for the markdown,
`source_pdf` for the master, and only the second is touched here.

Modes:

    copy    (default) the master is copied, the original left alone.
    move    the master is moved.
    rename  the master is renamed where it is, never relocated.

One rule overrides the mode: a master ALREADY inside the reference
library is moved within it, never copied. Copying a library file into
the same library produces two divergent copies of one paper, which is
the mess this tool exists to prevent.

Usage:
    python tools/file_reference.py --source <slug>              # dry run
    python tools/file_reference.py --source <slug> --apply
    python tools/file_reference.py --all --apply
    python tools/file_reference.py --source <slug> --mode move --apply

Every applied operation is appended to
`.maintenance/reference_filing.jsonl` with both paths and the file
digest, so a filing pass can be audited or undone by hand.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, SRC_DIR, parse_fm  # noqa: E402

JOURNAL = REPO_ROOT / ".maintenance" / "reference_filing.jsonl"

# Path segments that say nothing about the subject and must not become
# a library folder.
NOISE_SEGMENTS = {"articles", "sources", "general", "theses"}


def ref_dir_from_env() -> Path | None:
    val = os.environ.get("WIKI_REF_DIR", "").strip()
    return Path(val).expanduser() if val else None


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_master(fm: dict, slug: str) -> Path | None:
    """The master PDF a source page points at, wherever it lives."""
    val = str((fm or {}).get("source_pdf") or "").strip()
    if val:
        p = Path(val).expanduser()
        if not p.is_absolute():
            p = REPO_ROOT / p
        if p.is_file():
            return p
    for cand in sorted((REPO_ROOT / "raw").rglob(f"{slug}.pdf")):
        return cand
    return None


MIN_PREFIX = 4          # shortest overlap accepted as "the same folder"
MAX_LIB_DEPTH = 2       # how deep to look for an existing folder


def library_folders(ref_dir: Path) -> list:
    """Existing folders in the library, as paths relative to it.

    Depth-capped: the library is organised two levels deep, and matching
    deeper would file a paper somewhere nobody browses.
    """
    out = []
    if not ref_dir.is_dir():
        return out
    for depth in range(1, MAX_LIB_DEPTH + 1):
        for d in sorted(ref_dir.glob("/".join(["*"] * depth))):
            if d.is_dir() and not d.name.startswith("."):
                out.append(d.relative_to(ref_dir))
    return out


def match_folder(segment: str, folders: list):
    """An existing library folder meaning the same thing as `segment`, or None.

    The wiki and the library grew separate vocabularies for the same
    shelves - `methodology` here, `Methodo` there; `eeg-methods` here,
    `EEG` there. Matching only on equality would file papers into a
    second, parallel set of folders and split the library in two, which
    is the failure this whole step exists to avoid. So: exact match
    first, then a prefix overlap of at least MIN_PREFIX characters in
    either direction. Shallowest folder wins: a root shelf named
    `Methodo/` is the general one, while `BCI/Methodo/` is the
    BCI-specific niche and would misfile a statistics paper.
    """
    seg = segment.lower().replace("_", "-")
    ordered = sorted(folders, key=lambda f: (len(f.parts), str(f)))
    for folder in ordered:
        name = folder.name.lower().replace("_", "-")
        if name == seg:
            return folder
    for folder in ordered:
        name = folder.name.lower().replace("_", "-")
        if len(name) >= MIN_PREFIX and (seg.startswith(name) or name.startswith(seg)):
            return folder
    return None


def theme_candidates(page: Path, fm: dict) -> list:
    """Words that could name this paper's shelf, most specific first.

    Two sources, because they fail in different places. The page's path
    under `sources/` carries the subject for an empirical paper
    (`articles/bci/`), but for a review it carries the STUDY DESIGN
    (`articles/reviews/systematic/`), which no subject-organised library
    has a shelf for. The frontmatter's intervention family and domain
    carry the subject in both cases.
    """
    out = []
    try:
        rel = page.parent.relative_to(SRC_DIR)
        out += [s for s in reversed(rel.parts) if s and s.lower() not in NOISE_SEGMENTS]
    except ValueError:
        pass
    for key in ("intervention_subfamily", "intervention_family"):
        val = str((fm or {}).get(key) or "").strip()
        if val:
            out.append(val)
    for key in ("domain", "tags"):
        val = (fm or {}).get(key) or []
        if isinstance(val, str):
            val = [val]
        out += [str(v).strip() for v in val if str(v).strip()]
    seen, uniq = set(), []
    for c in out:
        if c.lower() not in seen:
            seen.add(c.lower())
            uniq.append(c)
    return uniq


def theme_for(page: Path, fm: dict, ref_dir: Path, allow_new: bool = False):
    """(library sub-path, is_new) for a source page.

    Walks the candidate words and takes the first that names a shelf the
    library ALREADY has. With no match the PDF goes to the library root
    rather than inventing a category: the taxonomy of that library is the
    user's, and a tool that adds folders to it every time the wiki uses
    a word it does not know would fragment it. `--allow-new-folders`
    opts into the opposite.
    """
    folders = library_folders(ref_dir)
    for candidate in theme_candidates(page, fm):
        hit = match_folder(candidate, folders)
        if hit is not None:
            return hit, False
    if allow_new:
        cands = theme_candidates(page, fm)
        return (Path(cands[0]), True) if cands else (Path(""), False)
    return Path(""), False


def already_in_library(ref_dir: Path, slug: str, target: Path):
    """A copy of this paper already shelved in the library, or None.

    Searched by file name, which is cheap. Without it, `copy` mode
    duplicates a paper that is already in the library under the same
    name in another folder - the first thing this tool did on its first
    real run. The answer is to MOVE that copy to the right shelf rather
    than add a second one.

    A duplicate still carrying a human name ("Mensen 2013 TFCE.pdf")
    cannot be found this way; catching those would mean hashing the
    whole library on every ingest, which is not worth it here.
    """
    for hit in sorted(ref_dir.rglob(f"{slug}.pdf")):
        if hit != target and hit.is_file():
            return hit
    return None


def plan(slug: str, ref_dir: Path, mode: str, allow_new: bool = False) -> dict:
    """What would happen to one source's master PDF. No side effects."""
    hits = sorted(SRC_DIR.rglob(f"{slug}.md"))
    out = {"slug": slug, "action": "skip", "detail": "", "src": None, "dst": None}
    if not hits:
        out["detail"] = "no source page"
        return out
    page = hits[0]
    fm, _ = parse_fm(page.read_text(encoding="utf-8"))
    master = resolve_master(fm, slug)
    if master is None:
        out["detail"] = "no master PDF (source_pdf missing or broken)"
        return out
    out["src"] = str(master)

    inside = ref_dir in master.parents
    new_folder = False
    if mode == "rename":
        target = master.with_name(f"{slug}.pdf")
    else:
        theme, new_folder = theme_for(page, fm, ref_dir, allow_new)
        target = ref_dir / theme / f"{slug}.pdf"
    out["dst"] = str(target)
    out["new_folder"] = new_folder

    shelved = None if mode == "rename" else already_in_library(ref_dir, slug, target)

    if target == master or target.exists():
        try:
            same = target == master or digest(target) == digest(master)
        except OSError:
            same = False
        if not same:
            out["action"] = "conflict"
            out["detail"] = ("a DIFFERENT file already holds that name - "
                             "resolve by hand")
            return out
        if shelved is not None:
            # Correctly filed, but a second copy of the same paper sits
            # elsewhere in the library. Reported, never deleted: removing
            # a file from someone's library is their call, not a tool's.
            out["action"] = "duplicate"
            out["detail"] = (f"filed correctly, but another copy is at {shelved} "
                             "- delete it by hand if it is redundant")
            return out
        out["action"] = "ok"
        out["detail"] = "already named and filed"
        return out

    # A master already in the library is moved within it, never copied:
    # copying would leave two divergent copies of one paper inside the
    # very library this is meant to keep tidy. Same reasoning when the
    # paper is already shelved elsewhere under this slug - then it is
    # that copy that gets moved, not the master that gets duplicated.
    if shelved is not None:
        out["src"] = str(shelved)
        out["action"] = "move"
        out["detail"] = (f"move -> {target} (already shelved at {shelved.parent}, "
                         "moved rather than duplicated)")
        out["page"] = str(page.relative_to(REPO_ROOT))
        return out

    effective = "move" if (inside and mode == "copy") else mode
    out["action"] = effective
    out["detail"] = (
        f"{effective} -> {target}"
        + (" (already in the library, so moved not copied)" if effective != mode else "")
        + (" [CREATES a new library folder]" if new_folder
           else (" (no matching shelf, filed at the library root)"
                 if mode != "rename" and target.parent == ref_dir else ""))
    )
    out["page"] = str(page.relative_to(REPO_ROOT))
    return out


def apply(step: dict) -> str:
    """Perform one planned operation and repoint the page. Returns a note."""
    src, dst = Path(step["src"]), Path(step["dst"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    before = digest(src)
    if step["action"] == "copy":
        shutil.copy2(src, dst)
    else:                                   # move / rename
        shutil.move(str(src), str(dst))

    page = REPO_ROOT / step["page"]
    text = page.read_text(encoding="utf-8")
    fm, body = parse_fm(text)
    old_pointer = str((fm or {}).get("source_pdf") or "")
    if old_pointer:
        text = text.replace(old_pointer, str(dst), 1)
        page.write_text(text, encoding="utf-8")

    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "slug": step["slug"], "action": step["action"],
            "from": str(src), "to": str(dst), "sha256": before,
            "page": step["page"],
        }, ensure_ascii=False) + "\n")
    return f"{step['action']} -> {dst}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--source", help="one slug")
    g.add_argument("--all", action="store_true", help="every source page")
    ap.add_argument("--ref-dir", help="reference library (default: $WIKI_REF_DIR)")
    ap.add_argument("--mode", choices=["copy", "move", "rename"], default=None,
                    help="default: $WIKI_REF_MODE, else copy")
    ap.add_argument("--allow-new-folders", action="store_true",
                    help="create a library folder when no existing shelf matches "
                         "(default: file at the library root instead)")
    ap.add_argument("--apply", action="store_true", help="write (default is a dry run)")
    args = ap.parse_args()

    ref_dir = Path(args.ref_dir).expanduser() if args.ref_dir else ref_dir_from_env()
    mode = args.mode or os.environ.get("WIKI_REF_MODE", "copy").strip() or "copy"

    if ref_dir is None:
        sys.exit("No reference library. Pass --ref-dir or set WIKI_REF_DIR "
                 "(the SessionStart hook asks for it once and persists it).")
    if not ref_dir.is_dir():
        sys.exit(f"Reference library does not exist: {ref_dir}")

    slugs = ([p.stem for p in sorted(SRC_DIR.rglob("*.md"))
              if p.name not in {"index.md", "log.md", "overview.md"}]
             if args.all else [args.source.strip().removesuffix(".md")])

    print(f"file_reference: {len(slugs)} source(s), mode={mode}, "
          f"{'APPLY' if args.apply else 'dry run'}")
    print(f"  library: {ref_dir}")
    print()

    counts = {}
    for slug in slugs:
        step = plan(slug, ref_dir, mode, args.allow_new_folders)
        counts[step["action"]] = counts.get(step["action"], 0) + 1
        if step["action"] in ("copy", "move", "rename", "conflict", "duplicate"):
            note = step["detail"]
            if args.apply and step["action"] not in ("conflict", "duplicate"):
                try:
                    note = apply(step)
                except OSError as e:
                    note = f"FAILED: {e}"
                    counts["error"] = counts.get("error", 0) + 1
            print(f"  [{step['action']:>8}] {slug}: {note}")

    print()
    print("  " + " | ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if args.apply and JOURNAL.exists():
        print(f"  journal: {JOURNAL.relative_to(REPO_ROOT)}")
    return 1 if counts.get("conflict") or counts.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
