#!/usr/bin/env python3
"""Strip em dashes and en dashes from text, normalizing to plain hyphens.

House style rule: GraphBib never emits the em dash (U+2014) or the en dash
(U+2013). This tool is the deterministic fixer the `librarian` agent runs,
and the same routine the `lint` audit flags via tools/lint_cache.py (check
`em_dash`).

Replacements:
  - em dash (U+2014) -> ' - ' (whitespace-collapsing: 'a - b', 'a-b', 'a -b'
    all normalize to 'a - b'). Applied to BOTH .md and .py files (no code
    relies on a literal em dash).
  - en dash (U+2013) -> '-' (plain, so ranges like '10-20' stay tight).
    Applied to .md files ONLY. In .py / .json the en dash is left alone
    because it appears inside regex character classes (written with the
    escape \\u2013) that must keep matching en dashes in the immutable raw/
    corpus. The handful of .py output strings that emit an en dash are fixed
    by hand, not by this tool.

Scope:
    --scope vault   (default) the active wiki vault's *.md only
    --scope all     wiki/ + docs/ + .claude/ *.md, plus tools/ + pdf2md/ *.py
                    and root-level *.md. raw/ is NEVER touched (immutable).

Usage:
    python tools/strip_em_dash.py --check            # report only, exit 1 if any
    python tools/strip_em_dash.py                    # fix the active vault
    python tools/strip_em_dash.py --scope all        # repo-wide cleanup
    python tools/strip_em_dash.py path/a.md path/b.md  # explicit files
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR  # noqa: E402

EM_DASH = chr(0x2014)  # built from codepoint so no literal char lives in this file
EN_DASH = chr(0x2013)
EM_DASH_RE = re.compile(r"[ \t]*" + EM_DASH + r"[ \t]*")


def collect_files(scope):
    """Return the list of files in scope, excluding raw/ and .git/."""
    files = []
    if scope == "vault":
        roots_md = [WIKI_DIR]
        roots_py = []
        root_level_md = []
    else:  # all
        roots_md = [REPO_ROOT / "wiki", REPO_ROOT / "docs", REPO_ROOT / ".claude"]
        roots_py = [REPO_ROOT / "tools", REPO_ROOT / "pdf2md"]
        root_level_md = sorted(REPO_ROOT.glob("*.md"))
    for root in roots_md:
        if root.is_dir():
            files += root.rglob("*.md")
    for root in roots_py:
        if root.is_dir():
            files += root.rglob("*.py")
    files += root_level_md
    raw = REPO_ROOT / "raw"
    out = []
    seen = set()
    for f in files:
        if not f.is_file():
            continue
        try:
            f.relative_to(raw)
            continue  # under raw/ - never touch
        except ValueError:
            pass
        if f in seen:
            continue
        seen.add(f)
        out.append(f)
    return sorted(out)


def process(path, apply):
    """Return number of banned dashes in `path`; rewrite the file when apply=True.

    Em dashes are stripped everywhere; en dashes only in .md files (see module
    docstring - .py/.json en dashes live in regexes that must match raw/).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return 0
    is_md = path.suffix.lower() == ".md"
    n = text.count(EM_DASH) + (text.count(EN_DASH) if is_md else 0)
    if n and apply:
        new = EM_DASH_RE.sub(" - ", text)
        if is_md:
            new = new.replace(EN_DASH, "-")
        path.write_text(new, encoding="utf-8")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="explicit files (overrides --scope)")
    ap.add_argument("--scope", choices=["vault", "all"], default="vault")
    ap.add_argument("--check", action="store_true", help="report only, do not modify")
    args = ap.parse_args()

    if args.paths:
        files = [Path(p) for p in args.paths]
    else:
        files = collect_files(args.scope)

    total = 0
    hit_files = 0
    for f in files:
        n = process(f, apply=not args.check)
        if n:
            total += n
            hit_files += 1
            rel = f.relative_to(REPO_ROOT) if f.is_absolute() and str(f).startswith(str(REPO_ROOT)) else f
            verb = "found" if args.check else "fixed"
            print(f"  {verb} {n:>4}  {rel}", file=sys.stderr)

    if args.check:
        print(f"{total} em dash(es) across {hit_files} file(s).", file=sys.stderr)
        sys.exit(1 if total else 0)
    print(f"Replaced {total} em dash(es) across {hit_files} file(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
