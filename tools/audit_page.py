#!/usr/bin/env python3
"""Audit trail - git blame for a wiki page, mapped to ingest commits.

For a given wiki page, runs `git blame` and groups each line by the
commit that introduced it. Cross-references commits with
`wiki/log.md` (parsed for `## [YYYY-MM-DD] ingest | <Title>` markers)
to label which ingest each line came from.

Usage:
    python tools/audit_page.py wiki/concepts/MotorImagery.md
    python tools/audit_page.py wiki/concepts/MotorImagery.md --section "Empirical Evidence"

Useful for:
    - Defending a claim during a thesis review.
    - Identifying when a concept's definition shifted.
    - Untangling synthesis lines that reference multiple sources.
"""
import argparse
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR  # noqa: E402

LOG_HEADER_RE = re.compile(r"^##\s+\[(\d{4}-\d{2}-\d{2})\]\s+(\w+)\s*\|\s*(.+)$", re.MULTILINE)


def parse_log():
    """Parse wiki/log.md → dict[date -> list of (operation, title)]."""
    log_path = WIKI_DIR / "log.md"
    if not log_path.is_file():
        return {}
    text = log_path.read_text(encoding="utf-8")
    out = {}
    for m in LOG_HEADER_RE.finditer(text):
        date, op, title = m.group(1), m.group(2), m.group(3)
        out.setdefault(date, []).append((op, title.strip()))
    return out


def git_blame(path):
    """Return list of {line_num, commit, author, date, content}."""
    try:
        raw = subprocess.check_output(
            ["git", "blame", "--line-porcelain", str(path)],
            cwd=REPO_ROOT,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        sys.exit(f"git blame failed: {e}")

    blocks = []
    current = {}
    for line in raw.splitlines():
        if line.startswith("\t"):
            current["content"] = line[1:]
            blocks.append(current)
            current = {}
            continue
        if not current and re.match(r"^[0-9a-f]{40}", line):
            parts = line.split()
            current["commit"] = parts[0][:8]
            current["line_num"] = int(parts[2])
            continue
        if line.startswith("author "):
            current["author"] = line[7:]
        elif line.startswith("author-time "):
            current["timestamp"] = int(line[12:])
        elif line.startswith("summary "):
            current["summary"] = line[8:]
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page", help="Wiki page (e.g. wiki/concepts/MotorImagery.md)")
    ap.add_argument("--section", help="Restrict to a section (e.g. 'Empirical Evidence')")
    args = ap.parse_args()

    p = Path(args.page).resolve()
    if not p.is_file():
        sys.exit(f"Not a file: {p}")

    log_index = parse_log()
    blocks = git_blame(p)

    # Filter to a section if requested
    if args.section:
        text = p.read_text(encoding="utf-8")
        m = re.search(rf"^##\s+{re.escape(args.section)}\s*$", text, re.MULTILINE)
        if not m:
            sys.exit(f"Section '## {args.section}' not found in {p.name}")
        start_line = text[: m.start()].count("\n") + 1
        nxt = re.search(r"^##\s+", text[m.end():], re.MULTILINE)
        end_line = (start_line + text[m.end() : m.end() + nxt.start()].count("\n")) if nxt else len(blocks)
        blocks = [b for b in blocks if start_line <= b.get("line_num", 0) <= end_line]

    # Group by commit
    by_commit = OrderedDict()
    for b in blocks:
        c = b.get("commit", "?")
        by_commit.setdefault(c, []).append(b)

    print(f"# Audit trail - {p.relative_to(REPO_ROOT)}")
    if args.section:
        print(f"_Section: ## {args.section}_\n")
    print(f"\n{len(by_commit)} distinct commits across {len(blocks)} lines.\n")

    for commit, items in by_commit.items():
        first = items[0]
        ts = first.get("timestamp")
        date = ""
        if ts:
            from datetime import datetime, timezone
            date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        author = first.get("author", "?")
        summary = first.get("summary", "")
        log_match = ""
        if date and date in log_index:
            ops = [t for op, t in log_index[date] if op == "ingest"]
            if ops:
                log_match = f" - ingest: {ops[0]}"
        print(f"## {commit} ({date}) {author}")
        print(f"_{summary}_{log_match}")
        print(f"_{len(items)} lines_\n")
        for b in items[:5]:
            content = (b.get("content") or "").rstrip()
            if content:
                print(f"  L{b['line_num']:>4}  {content[:100]}")
        if len(items) > 5:
            print(f"  … and {len(items) - 5} more")
        print()


if __name__ == "__main__":
    main()
