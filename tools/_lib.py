"""Shared helpers for tools/* scripts.

Kept tiny on purpose: frontmatter parsing, source loading, regex constants.
Avoid heavy imports here so analyzer scripts stay fast to import.
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
WIKI_DIR = REPO_ROOT / "wiki"
SRC_DIR = WIKI_DIR / "sources"

WIKILINK_RE = re.compile(r"\[\[([A-Za-z0-9\-_/.]+)\]\]")
PAGE_REF_RE = re.compile(r"\(p\.\s*([0-9?]+)\)")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")


def parse_fm(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]
            except Exception:
                pass
    return {}, text


def load_sources(directory=None):
    """Return list of dicts: {slug, fm, body, path} for each source page.

    Recurses into subdirectories so the new thematic layout
    (articles/<family>/<subfamily>/, theses/<slug>/...) is supported.
    """
    d = directory or SRC_DIR
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.rglob("*.md")):
        if p.name.startswith(".") or p.name in {"index.md", "log.md", "overview.md"}:
            continue
        text = p.read_text(encoding="utf-8")
        fm, body = parse_fm(text)
        out.append({"slug": p.stem, "fm": fm, "body": body, "path": p})
    return out


def section(body, header):
    """Return the contents of `## header` until the next `## ` or EOF."""
    pat = re.compile(rf"^##\s+{re.escape(header)}\s*$", re.MULTILINE)
    m = pat.search(body)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^##\s+", body[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(body)
    return body[start:end].strip()
