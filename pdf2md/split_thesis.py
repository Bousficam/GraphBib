#!/usr/bin/env python3
"""Split a thesis Markdown file into per-chapter files.

Detection heuristics (in order, first match wins per heading):
  1. "# Chapter N[: Title]"          (English / French)
  2. "# Chapitre N[ : Titre]"
  3. "# N. Title" / "# N) Title"      (numbered headings)
  4. Named chapters: "# Introduction" | "# Literature Review" |
     "# Methods" | "# Results" | "# Discussion" | "# General Discussion" |
     "# Conclusion" | "# References"
  5. Custom: pass --pattern to override

Output structure:
  raw/theses/dupont-2023.md                ← original (untouched)
  raw/theses/dupont-2023/ch01-introduction.md
  raw/theses/dupont-2023/ch02-literature-review.md
  ...

Each chapter file inherits the thesis frontmatter and adds:
  chapter: N
  chapter_title: "..."
  parent_thesis: <thesis-slug>

Skips emitting a chapter that's < MIN_CHARS characters (avoids producing
empty files when headings appear in TOC pages).

Usage:
    python pdf2md/split_thesis.py raw/theses/dupont-2023.md
    python pdf2md/split_thesis.py raw/theses/dupont-2023.md --dry-run
    python pdf2md/split_thesis.py raw/theses/dupont-2023.md --output-dir custom/
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

MIN_CHARS = 1500  # below this a "chapter" is likely a section header in the TOC

NAMED_CHAPTERS = (
    "introduction",
    "literature review",
    "background",
    "theoretical framework",
    "methods",
    "methodology",
    "general methods",
    "results",
    "discussion",
    "general discussion",
    "conclusion",
    "general conclusion",
    "perspectives",
    "references",
    "bibliography",
    "appendix",
    "appendices",
)

CHAPTER_PATTERNS = [
    re.compile(r"^#\s+(?:chapter|chapitre)\s+(\d{1,2})\b[\s.:—–-]*(.*?)\s*$", re.IGNORECASE),
    re.compile(r"^#\s+(\d{1,2})\s*[.)\-:]\s+(.+?)\s*$"),
]


def parse_fm(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]
            except Exception:
                pass
    return {}, text


def slug(s, max_len=40):
    s = re.sub(r"[^\w\s-]", "", s.lower(), flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s[:max_len].rstrip("-") or "section"


def detect_chapter_heading(line):
    """Return (number, title) if line is a chapter heading, else None."""
    s = line.strip()
    if not s.startswith("# "):
        return None
    for pat in CHAPTER_PATTERNS:
        m = pat.match(s)
        if m:
            num = int(m.group(1))
            title = (m.group(2) or "").strip().rstrip(".:")
            return num, title
    # Named chapter (without number)
    body = s[2:].strip().lower().rstrip(":.")
    for name in NAMED_CHAPTERS:
        if body == name or body.startswith(name + " "):
            return None, body  # numberless
    return None


def split_into_chapters(body):
    """Walk the body line by line, returning a list of (heading_line, content)."""
    lines = body.splitlines(keepends=True)
    chapters = []
    current_heading = None
    current_buf = []
    fallback_num = 0

    def flush():
        if not current_buf:
            return
        text = "".join(current_buf)
        chapters.append((current_heading, text))

    for line in lines:
        det = detect_chapter_heading(line)
        if det is not None:
            flush()
            num, title = det
            if num is None:
                fallback_num += 1
                num = fallback_num
            else:
                fallback_num = max(fallback_num, num)
            current_heading = (num, title or line.strip().lstrip("# ").strip(), line)
            current_buf = [line]
        else:
            current_buf.append(line)

    flush()
    return chapters


def write_chapters(parent_path, parent_fm, chapters, output_dir, dry_run=False):
    parent_slug = parent_path.stem
    out_dir = output_dir or (parent_path.parent / parent_slug)

    written = []
    skipped = []
    front_chapter_buf = []

    for entry in chapters:
        heading, text = entry
        if heading is None:
            # Content before the first chapter heading (TOC / preamble)
            front_chapter_buf.append(text)
            continue
        num, title, _ = heading
        if len(text) < MIN_CHARS:
            skipped.append((num, title, len(text)))
            continue
        title_slug = slug(title) if title else f"section-{num:02d}"
        filename = f"ch{num:02d}-{title_slug}.md"
        out_path = out_dir / filename

        chapter_fm = dict(parent_fm)
        chapter_fm["chapter"] = num
        chapter_fm["chapter_title"] = title
        chapter_fm["parent_thesis"] = parent_slug
        chapter_fm["type"] = "source"
        chapter_fm.setdefault("tags", [])
        if "thesis-chapter" not in chapter_fm["tags"]:
            chapter_fm["tags"] = list(chapter_fm["tags"]) + ["thesis-chapter"]
        # Drop the original source_pdf (chapter is a slice of it; keep parent ref instead)
        chapter_fm["source_file"] = str(out_path).split("raw/", 1)[-1]
        if "raw/" in str(out_path):
            chapter_fm["source_file"] = "raw/" + chapter_fm["source_file"]

        fm_text = yaml.safe_dump(chapter_fm, allow_unicode=True, sort_keys=False).strip()
        body = f"---\n{fm_text}\n---\n\n{text.lstrip()}"

        if dry_run:
            print(f"  [dry] would write {out_path} ({len(text)} chars)")
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(body, encoding="utf-8")
            print(f"  ✓ {out_path} ({len(text)} chars)")
        written.append(out_path)

    return written, skipped, "".join(front_chapter_buf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("thesis", help="Path to the thesis Markdown file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--output-dir", help="Override output dir (default: <thesis>/ next to the file)")
    args = ap.parse_args()

    parent = Path(args.thesis).expanduser().resolve()
    if not parent.is_file():
        sys.exit(f"Not a file: {parent}")

    text = parent.read_text(encoding="utf-8")
    fm, body = parse_fm(text)

    chapters = split_into_chapters(body)
    if not any(h for h, _ in chapters):
        sys.exit("No chapter headings detected. Try editing the thesis MD to add `# Chapter N: Title` markers.")

    out_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None

    written, skipped, preamble = write_chapters(parent, fm, chapters, out_dir, dry_run=args.dry_run)

    print(f"\n=== {len(written)} chapter(s) {'would be ' if args.dry_run else ''}written ===")
    if skipped:
        print(f"  skipped (< {MIN_CHARS} chars):")
        for num, title, n in skipped:
            print(f"    ch{num:02d} {title!r} — {n} chars")
    if preamble.strip():
        print(f"  preamble (front matter / TOC): {len(preamble)} chars left in parent")


if __name__ == "__main__":
    main()
