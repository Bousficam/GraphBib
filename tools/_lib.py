"""Shared helpers for tools/* scripts.

Kept tiny on purpose: frontmatter parsing, source loading, regex constants.
Avoid heavy imports here so analyzer scripts stay fast to import.

Multi-vault resolution
----------------------

`WIKI_DIR` resolves to the active vault, picking by this priority:

  1. $WIKI_VAULT env var       → REPO_ROOT/wiki/$WIKI_VAULT
  2. Single sub-vault detected → REPO_ROOT/wiki/<the-only-vault>/
     (a sub-folder is a vault iff it contains `sources/`)
  3. Legacy flat layout        → REPO_ROOT/wiki/
     (when wiki/sources/ exists directly, no vault sub-folders)
  4. Multiple sub-vaults, no env var → REPO_ROOT/wiki/ (mode = "ambiguous";
     callers should detect this via ACTIVE_VAULT_MODE and prompt the user
     to set $WIKI_VAULT)
  5. Empty                     → REPO_ROOT/wiki/
"""
import os
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"


def _detect_active_vault():
    """Return (vault_dir, mode) where mode is one of:
    'env', 'single', 'legacy', 'empty', 'ambiguous'.
    """
    env_vault = os.environ.get("WIKI_VAULT", "").strip()
    if env_vault:
        return WIKI_ROOT / env_vault, "env"
    if not WIKI_ROOT.is_dir():
        return WIKI_ROOT, "empty"
    if (WIKI_ROOT / "sources").is_dir():
        return WIKI_ROOT, "legacy"
    vaults = [d for d in WIKI_ROOT.iterdir()
              if d.is_dir() and not d.name.startswith(".")
              and (d / "sources").is_dir()]
    if len(vaults) == 1:
        return vaults[0], "single"
    if len(vaults) > 1:
        return WIKI_ROOT, "ambiguous"
    return WIKI_ROOT, "empty"


WIKI_DIR, ACTIVE_VAULT_MODE = _detect_active_vault()
SRC_DIR = WIKI_DIR / "sources"


def active_vault_name():
    """Slug of the currently-resolved vault, or None for legacy / empty / ambiguous."""
    if ACTIVE_VAULT_MODE in ("env", "single") and WIKI_DIR != WIKI_ROOT:
        return WIKI_DIR.name
    return None


def list_vaults():
    """All sub-folders of wiki/ that look like vaults (contain sources/)."""
    if not WIKI_ROOT.is_dir():
        return []
    return sorted(
        d.name for d in WIKI_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "sources").is_dir()
    )


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
