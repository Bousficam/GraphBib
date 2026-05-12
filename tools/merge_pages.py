#!/usr/bin/env python3
"""Merge two wiki pages: append source into target, rewrite every wikilink.

Used by the `deduplicator` sub-agent (and the librarian) to mechanically
execute a merge decision the LLM has already made. The script is
deterministic: no judgment about whether the merge is *appropriate*,
only how to apply it cleanly.

Operation (dry-run by default; `--apply` to actually do it):

  1. **Frontmatter union** — target keeps its title and primary fields.
     Source's title and aliases are added to target's `aliases:`.
     `tags`, `cites`, `methods`, `domain`, `replication_of` (when lists)
     are unioned. Scalar fields not on target are copied from source.
  2. **Body append** — source body is appended under a new section:
     `## Merged from [[source-slug]] (YYYY-MM-DD)`. A comment marker
     `<!-- merged-from: source-slug -->` is added for audit.
  3. **Wikilink rewrite** — every `.md` in the wiki has
     `[[source-slug]]`, `[[source-slug|alias]]`, `[[source-slug#section]]`
     replaced with the target-slug equivalent.
  4. **Source page deletion** — `wiki/<kind>/<source-slug>.md` is
     removed (only after the rewrites succeed).
  5. **Audit log entry** — appends to `wiki/log.md`.

CLI:

    # Dry-run (default): shows planned changes, makes nothing
    python tools/merge_pages.py SOURCE_SLUG TARGET_SLUG

    # Apply: actually merges + rewrites + deletes
    python tools/merge_pages.py SOURCE_SLUG TARGET_SLUG --apply

    # Restrict the rewrite scope (default: whole wiki/)
    python tools/merge_pages.py SOURCE TARGET --scope wiki/concepts/

The slugs are page stems (no .md, no path). The script searches
wiki/concepts/, wiki/methods/, wiki/interventions/ to locate them.
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR, parse_fm  # noqa: E402

import yaml  # noqa: E402

KINDS = ("concepts", "methods", "interventions")

UNION_LIST_FIELDS = ("tags", "cites", "methods", "domain", "aliases", "interventions")


def _find_page(slug: str) -> Path | None:
    for kind in KINDS:
        candidate = WIKI_DIR / kind / f"{slug}.md"
        if candidate.exists():
            return candidate
        for nested in (WIKI_DIR / kind).rglob(f"{slug}.md"):
            return nested
    return None


def _union_fm(src_fm: dict, tgt_fm: dict, src_slug: str) -> dict:
    out = dict(tgt_fm)
    for f in UNION_LIST_FIELDS:
        a = src_fm.get(f) or []
        b = tgt_fm.get(f) or []
        if not isinstance(a, list) or not isinstance(b, list):
            continue
        seen = []
        for item in (*b, *a):
            if item not in seen:
                seen.append(item)
        out[f] = seen

    src_title = (src_fm.get("title") or src_slug).strip()
    aliases = out.get("aliases") or []
    if src_title and src_title not in aliases and src_title != (tgt_fm.get("title") or ""):
        aliases = [*aliases, src_title]
    out["aliases"] = aliases

    for k, v in src_fm.items():
        if k in UNION_LIST_FIELDS or k == "title":
            continue
        if k not in out or not out[k]:
            out[k] = v
    return out


def _format_fm(fm: dict) -> str:
    return "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip() + "\n---\n\n"


def _merge_body(src_slug: str, src_body: str, tgt_body: str) -> str:
    today = dt.date.today().isoformat()
    header = f"\n\n## Merged from [[{src_slug}]] ({today})\n\n<!-- merged-from: {src_slug} -->\n\n"
    return tgt_body.rstrip() + header + src_body.lstrip()


def _wikilink_replace_re(src_slug: str) -> re.Pattern:
    safe = re.escape(src_slug)
    return re.compile(rf"\[\[{safe}(?P<suffix>[#|][^\]]*)?\]\]")


def _rewrite_links_in_file(path: Path, src_slug: str, tgt_slug: str, apply: bool) -> int:
    text = path.read_text(encoding="utf-8")
    pat = _wikilink_replace_re(src_slug)

    def repl(m):
        suffix = m.group("suffix") or ""
        return f"[[{tgt_slug}{suffix}]]"

    new_text, n = pat.subn(repl, text)
    if n and apply:
        path.write_text(new_text, encoding="utf-8")
    return n


def _append_log(src_slug: str, tgt_slug: str, apply: bool) -> None:
    if not apply:
        return
    log = WIKI_DIR / "log.md"
    if not log.exists():
        return
    line = f"- {dt.date.today().isoformat()} — merged [[{src_slug}]] into [[{tgt_slug}]] (tools/merge_pages.py)\n"
    log.write_text(log.read_text(encoding="utf-8").rstrip() + "\n" + line, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source_slug", help="Page to remove (content folded into target)")
    parser.add_argument("target_slug", help="Page to keep (receives content)")
    parser.add_argument("--apply", action="store_true", help="Actually perform the merge (default: dry-run)")
    parser.add_argument("--scope", default=str(WIKI_DIR), help="Limit wikilink rewrite to a subtree")
    args = parser.parse_args()

    if args.source_slug == args.target_slug:
        sys.exit("source and target slugs are identical")

    src = _find_page(args.source_slug)
    tgt = _find_page(args.target_slug)
    if not src:
        sys.exit(f"source page not found: {args.source_slug}")
    if not tgt:
        sys.exit(f"target page not found: {args.target_slug}")

    src_fm, src_body = parse_fm(src.read_text(encoding="utf-8"))
    tgt_fm, tgt_body = parse_fm(tgt.read_text(encoding="utf-8"))

    merged_fm = _union_fm(src_fm, tgt_fm, args.source_slug)
    merged_body = _merge_body(args.source_slug, src_body, tgt_body)
    merged_text = _format_fm(merged_fm) + merged_body

    scope_root = Path(args.scope).resolve()
    rewrites: dict[str, int] = {}
    for p in scope_root.rglob("*.md"):
        if p == src or p == tgt:
            continue
        n = _rewrite_links_in_file(p, args.source_slug, args.target_slug, apply=args.apply)
        if n:
            rewrites[str(p.relative_to(REPO_ROOT))] = n

    if args.apply:
        tgt.write_text(merged_text, encoding="utf-8")
        src.unlink()
        _append_log(args.source_slug, args.target_slug, apply=True)
        verb = "MERGED"
    else:
        verb = "WOULD MERGE"

    print(f"{verb} [[{args.source_slug}]] → [[{args.target_slug}]]")
    print(f"  source page : {src.relative_to(REPO_ROOT)}  ({len(src_body)} chars body)")
    print(f"  target page : {tgt.relative_to(REPO_ROOT)}  ({len(tgt_body)} chars → {len(merged_body)} chars)")
    print(f"  frontmatter : aliases now {merged_fm.get('aliases', [])}")
    print(f"  tags        : {merged_fm.get('tags', [])}")
    print(f"  wikilink rewrites across scope ({scope_root.relative_to(REPO_ROOT)}):")
    if not rewrites:
        print("    (none)")
    else:
        for path, n in sorted(rewrites.items()):
            print(f"    {path:60s} {n} link(s)")
    if not args.apply:
        print("\nDry-run only — re-run with --apply to write changes.")


if __name__ == "__main__":
    main()
