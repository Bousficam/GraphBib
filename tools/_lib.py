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

`RAW_DIR` mirrors the wiki vault — the raw inputs for a vault live at
`raw/<vault>/{papers,theses,books,notes}/`. Detection follows the same
$WIKI_VAULT env var and falls back to the same auto-detection rules:

  1. $WIKI_VAULT env var → REPO_ROOT/raw/$WIKI_VAULT
  2. Single raw vault    → REPO_ROOT/raw/<the-only-vault>/
     (a sub-folder is a raw vault iff it contains `papers/`)
  3. Legacy flat layout  → REPO_ROOT/raw/
     (when raw/papers/ exists directly, no vault sub-folders)
  4. Ambiguous           → REPO_ROOT/raw/ (callers should error)
  5. Empty               → REPO_ROOT/raw/

Wiki and raw share the same vault name (they describe the same
research domain — raw is the input, wiki is the ingested output).
"""
import json
import os
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"
RAW_ROOT = REPO_ROOT / "raw"
DATA_DIR = REPO_ROOT / "tools" / "data"
DOMAIN_FILE = DATA_DIR / "domain.json"


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


def _detect_active_raw():
    """Return (raw_dir, mode) — same modes as `_detect_active_vault`.

    Uses the same $WIKI_VAULT env var as the wiki side since raw and
    wiki share the vault concept (raw = inputs, wiki = ingested
    outputs of the same domain).
    """
    env_vault = os.environ.get("WIKI_VAULT", "").strip()
    if env_vault:
        return RAW_ROOT / env_vault, "env"
    if not RAW_ROOT.is_dir():
        return RAW_ROOT, "empty"
    if (RAW_ROOT / "papers").is_dir():
        return RAW_ROOT, "legacy"
    vaults = [d for d in RAW_ROOT.iterdir()
              if d.is_dir() and not d.name.startswith(".")
              and (d / "papers").is_dir()]
    if len(vaults) == 1:
        return vaults[0], "single"
    if len(vaults) > 1:
        return RAW_ROOT, "ambiguous"
    return RAW_ROOT, "empty"


WIKI_DIR, ACTIVE_VAULT_MODE = _detect_active_vault()
SRC_DIR = WIKI_DIR / "sources"

RAW_DIR, ACTIVE_RAW_MODE = _detect_active_raw()


def raw_subdir(name):
    """Return RAW_DIR/<name> (e.g. raw_subdir('papers')).

    The four canonical sub-folders are `papers`, `theses`, `books`,
    `notes`. Callers should `.mkdir(parents=True, exist_ok=True)` when
    writing.
    """
    return RAW_DIR / name


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


def list_raw_vaults():
    """All sub-folders of raw/ that look like raw vaults (contain papers/)."""
    if not RAW_ROOT.is_dir():
        return []
    return sorted(
        d.name for d in RAW_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "papers").is_dir()
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


def load_domain(section_name=None):
    """Load the machine-readable domain vocabulary from tools/data/domain.json.

    Returns the whole config dict (keys starting with `_` stripped), or one
    section if `section_name` is given. Returns {} when the file is missing,
    unparseable, or the section is absent. The shipped default is the neutral
    baseline (all sections empty) — domain-specific tools should detect an
    empty section and print a helpful "configure domain.json" message rather
    than assuming a domain.
    """
    if not DOMAIN_FILE.is_file():
        return {}
    try:
        data = json.loads(DOMAIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    data = {k: v for k, v in data.items() if not k.startswith("_")}
    if section_name is None:
        return data
    return data.get(section_name, {})


def compile_lexicon(entries):
    """Compile a regions/tracts-style section into matchers.

    `entries` is {key: {"canonical": str, "aliases": [plain strings]}}.
    Returns {key: {"label": str, "patterns": [compiled regex]}} with each
    alias escaped and matched on word boundaries, case-insensitive.
    """
    out = {}
    for key, entry in (entries or {}).items():
        if not isinstance(entry, dict):
            continue
        aliases = entry.get("aliases", []) or []
        out[key] = {
            "label": entry.get("canonical", key),
            "patterns": [re.compile(rf"\b{re.escape(a)}\b", re.IGNORECASE) for a in aliases],
        }
    return out


def compile_fragments(mapping):
    """Compile a {key: [regex fragments]} section into {key: compiled regex}.

    Fragments are OR-joined raw (NOT escaped), so numeric patterns like
    r">\\s*6\\s*month" work. A bare string value is accepted too.
    """
    out = {}
    for key, frags in (mapping or {}).items():
        if isinstance(frags, str):
            frags = [frags]
        if not frags:
            continue
        out[key] = re.compile("|".join(frags), re.IGNORECASE)
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
