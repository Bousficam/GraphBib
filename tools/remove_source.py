#!/usr/bin/env python3
"""Find and (optionally) remove every reference to a source across the wiki.

Use case: a paper was ingested by mistake (wrong scope, retracted,
duplicate). This tool surfaces every place its slug or DOI is referenced,
proposes edits, and applies them only after --apply.

Usage:

    # Default: dry-run, prints every file that mentions the slug
    python tools/remove_source.py cervera-2020

    # Apply the edits (after dry-run review)
    python tools/remove_source.py cervera-2020 --apply

    # Strict mode: also remove sub-claim bullets that become orphaned
    python tools/remove_source.py cervera-2020 --apply --strict

What it does
============

For the source page `wiki/sources/.../<slug>.md`:
  1. Find every `[[<slug>]]` wikilink across `wiki/`.
  2. Find every reference to the source's DOI (from its frontmatter)
     in other source pages' `cites:` arrays.
  3. Find mentions in `wiki/index.md`, `wiki/log.md`, `wiki/overview.md`.
  4. Find references in `## Cited By` sections of other source pages.
  5. Surface every match with line context (dry-run) OR rewrite the
     line / drop the bullet (--apply).
  6. Delete the source file itself.

Safety
======

- Default is `--dry-run` (only print, no edit, no delete).
- After `--apply`, the agent is expected to commit the changes via git
  so the user can revert (`git revert` or `git reset --hard HEAD~1`).
- `--strict` removes orphaned sub-claim bullets in concept pages
  (bullets where `[[<slug>]]` was the SOLE supporting source). Without
  --strict, the wikilink is removed but the surrounding sentence /
  bullet is kept (which may produce dangling claims — manual review
  needed).
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR  # noqa: E402


def parse_fm(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5:], text[:end + 5]
            except Exception:
                pass
    return {}, text, ""


def serialize_fm(fm):
    return "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip() + "\n---\n"


def find_source_page(slug):
    """Locate wiki/sources/.../<slug>.md."""
    src_dir = WIKI_DIR / "sources"
    if not src_dir.is_dir():
        return None
    for p in src_dir.rglob(f"{slug}.md"):
        return p
    return None


def get_source_doi(source_path):
    text = source_path.read_text(encoding="utf-8")
    fm, _, _ = parse_fm(text)
    return (fm.get("doi") or "").strip().lower()


def find_wikilink_refs(slug):
    """Return list of (path, line_num, line) for every [[slug]] across wiki/."""
    token = f"[[{slug}]]"
    out = []
    for p in WIKI_DIR.rglob("*.md"):
        if p.name == ".gitkeep":
            continue
        try:
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if token in line:
                    out.append((p, i, line))
        except Exception:
            continue
    return out


def find_doi_in_cites(target_doi):
    """Return list of (path, fm) where the source's frontmatter `cites:`
    contains the target DOI.
    """
    out = []
    if not target_doi:
        return out
    src_dir = WIKI_DIR / "sources"
    if not src_dir.is_dir():
        return out
    for p in src_dir.rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        fm, _, _ = parse_fm(text)
        cites = fm.get("cites") or []
        if any(str(c).lower() == target_doi for c in cites):
            out.append((p, fm))
    return out


def remove_wikilink(line, slug, strict=False):
    """Remove `[[slug]]` from a line. Returns (new_line, drop_line_bool).

    Heuristics for dropping:
    - If line is a bullet of the form "- [[slug]] (p. ?) — …"
      and slug was the SOLE wikilink, drop the bullet (strict).
    - Otherwise, just remove the [[slug]] token, leaving the rest.
    """
    token = f"[[{slug}]]"
    if token not in line:
        return line, False

    # If the bullet's only wikilink is this one and strict, drop it
    wls = re.findall(r"\[\[([^\]]+)\]\]", line)
    if strict and line.lstrip().startswith("- ") and len(wls) == 1 and wls[0] == slug:
        return "", True

    # Soft remove: drop the wikilink and clean up surrounding punctuation
    cleaned = line.replace(token, "")
    cleaned = re.sub(r"\(\s*p\.\s*[?\d]+\s*\)\s*", "", cleaned, count=1)
    cleaned = re.sub(r"\s+,\s+,", ", ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).rstrip(", ").rstrip()
    if not cleaned.strip("- ").strip():
        return "", True
    return cleaned, False


def apply_wikilink_removals(refs, slug, strict, dry_run):
    """For each (path, line_num, line) ref, rewrite the file."""
    edits_per_file = {}
    for p, ln, _ in refs:
        edits_per_file.setdefault(p, []).append(ln)

    for p, lines_to_edit in edits_per_file.items():
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        new_lines = []
        edits_applied = []
        for i, line in enumerate(lines, 1):
            if i in lines_to_edit:
                new_line, drop = remove_wikilink(line.rstrip("\n"), slug, strict=strict)
                if drop:
                    edits_applied.append(("drop", i, line.rstrip("\n")))
                    continue  # drop the line entirely
                if new_line != line.rstrip("\n"):
                    edits_applied.append(("rewrite", i, line.rstrip("\n"), new_line))
                    new_lines.append(new_line + "\n")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        if dry_run:
            print(f"\n  would edit {p.relative_to(REPO_ROOT)}:")
            for ed in edits_applied:
                if ed[0] == "drop":
                    print(f"    - L{ed[1]} drop: {ed[2][:120]}")
                else:
                    print(f"    - L{ed[1]} rewrite:")
                    print(f"        before: {ed[2][:120]}")
                    print(f"        after:  {ed[3][:120]}")
        else:
            p.write_text("".join(new_lines), encoding="utf-8")
            print(f"  ✓ edited {p.relative_to(REPO_ROOT)} ({len(edits_applied)} changes)")


def remove_doi_from_cites(refs_doi, target_doi, dry_run):
    """For each source page whose frontmatter cites: contains target_doi,
    remove the entry.
    """
    for p, fm in refs_doi:
        new_cites = [c for c in fm.get("cites", []) if str(c).lower() != target_doi]
        new_curated = [c for c in fm.get("cites_curated", []) if str(c).lower() != target_doi]
        if dry_run:
            print(f"  would drop {target_doi} from cites: in {p.relative_to(REPO_ROOT)}")
        else:
            text = p.read_text(encoding="utf-8")
            _, body, _ = parse_fm(text)
            fm["cites"] = new_cites
            if new_curated != fm.get("cites_curated", []):
                fm["cites_curated"] = new_curated
            p.write_text(serialize_fm(fm) + "\n" + body.lstrip(), encoding="utf-8")
            print(f"  ✓ dropped DOI from cites: in {p.relative_to(REPO_ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="Source slug to remove (e.g. cervera-2020)")
    ap.add_argument("--apply", action="store_true",
                    help="Actually apply the edits and delete the source file (default: dry-run)")
    ap.add_argument("--strict", action="store_true",
                    help="Drop bullets where the slug was the SOLE wikilink (orphan claim cleanup)")
    args = ap.parse_args()

    slug = args.slug.strip()
    source_path = find_source_page(slug)
    if not source_path:
        sys.exit(f"Source not found: wiki/sources/.../{slug}.md")

    target_doi = get_source_doi(source_path)
    print(f"Target source: {source_path.relative_to(REPO_ROOT)}")
    print(f"DOI: {target_doi or '(none)'}")

    print(f"\n=== Finding [[{slug}]] wikilinks across wiki/ ===")
    wl_refs = find_wikilink_refs(slug)
    print(f"  {len(wl_refs)} matches in {len(set(p for p, _, _ in wl_refs))} files")

    print(f"\n=== Finding DOI {target_doi} in source frontmatter cites: ===")
    doi_refs = find_doi_in_cites(target_doi) if target_doi else []
    print(f"  {len(doi_refs)} source pages")

    if not args.apply:
        print(f"\n=== DRY-RUN: showing edits that would be made ===")
        apply_wikilink_removals(wl_refs, slug, args.strict, dry_run=True)
        remove_doi_from_cites(doi_refs, target_doi, dry_run=True)
        print(f"\n  would delete {source_path.relative_to(REPO_ROOT)}")
        print(f"\nRe-run with --apply to actually remove. Commit your wiki changes")
        print(f"in git first so you can revert if needed.")
        return

    print(f"\n=== APPLYING edits ===")
    apply_wikilink_removals(wl_refs, slug, args.strict, dry_run=False)
    remove_doi_from_cites(doi_refs, target_doi, dry_run=False)

    source_path.unlink()
    print(f"  ✓ deleted {source_path.relative_to(REPO_ROOT)}")

    print(f"\n=== Done ===")
    print(f"Now run: python tools/update_cited_by.py")
    print(f"Then commit with a message like: 'remove source: {slug} (mistaken ingest)'")


if __name__ == "__main__":
    main()
