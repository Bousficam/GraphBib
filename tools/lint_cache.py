#!/usr/bin/env python3
"""Cache + deterministic checks for the lint sub-agent.

Two roles in one small module:

1. **Cache** - store per (sha256_of_file, check_name, agent_version)
   results so that re-running lint on unchanged content is free.
   Cache file: `tools/.cache/lint_state.json`.

2. **Deterministic checks** - pure-Python audits over wiki frontmatter
   and bodies. No LLM needed, fast, run every time the lint agent is
   invoked. The lint sub-agent reserves its LLM budget for the semantic
   checks (concept-definition compatibility, cross-source contradictions,
   CONSORT compliance) which are cached.

CLI:

    # Deterministic checks (always run, JSON output)
    python tools/lint_cache.py check
    python tools/lint_cache.py check --severity blocking
    python tools/lint_cache.py check --paths wiki/sources/articles/bci/

    # Cache inspection / management
    python tools/lint_cache.py cache --status              # entries / size
    python tools/lint_cache.py cache --gc                  # drop entries whose file no longer exists
    python tools/lint_cache.py cache --invalidate <name>   # invalidate one check across all files

The lint sub-agent calls `check` to surface deterministic findings and
reads the cache JSON directly to decide which semantic checks need
re-running (sha256 changed or agent_version bumped).
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR, SRC_DIR  # noqa: E402

CACHE_DIR = REPO_ROOT / "tools" / ".cache"
CACHE_FILE = CACHE_DIR / "lint_state.json"

CURRENT_AGENT_VERSION = "2026-05-v1"

EM_DASH = chr(0x2014)  # codepoints, not literals, so this file stays dash-clean
EN_DASH = chr(0x2013)


def em_dash_findings(body):
    """House-style rule: no em dash or en dash in wiki output. Flag any present."""
    em = body.count(EM_DASH)
    en = body.count(EN_DASH)
    if not (em or en):
        return []
    return [{
        "check": "em_dash",
        "pass": False,
        "severity": "WARNING",
        "details": f"{em} em dash(es) + {en} en dash(es) present; "
                   f"replace with hyphens (run python tools/strip_em_dash.py)",
    }]


# ============================================================================
# Cache primitives
# ============================================================================

def file_sha256(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"agent_version": CURRENT_AGENT_VERSION, "entries": {}}


def save_cache(cache):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_check_result(cache, sha, check_name, agent_version):
    entry = cache["entries"].get(sha)
    if not entry:
        return None
    chk = entry.get("checks", {}).get(check_name)
    if not chk:
        return None
    if chk.get("agent_version") != agent_version:
        return None
    return chk


def put_check_result(cache, sha, file_path, check_name, agent_version, result):
    if sha not in cache["entries"]:
        cache["entries"][sha] = {"checks": {}}
    e = cache["entries"][sha]
    e["path"] = str(file_path)
    e["last_linted"] = datetime.now(timezone.utc).isoformat()
    e.setdefault("checks", {})
    e["checks"][check_name] = {
        "agent_version": agent_version,
        "pass": bool(result.get("pass", False)),
        "severity": result.get("severity", "INFO"),
        "details": result.get("details", ""),
    }


def gc_cache(cache):
    """Drop entries whose file path no longer exists. Same-content moved
    files keep their entry (path is updated when the agent re-lints them).
    """
    drop = []
    for sha, entry in list(cache["entries"].items()):
        path = entry.get("path")
        if not path or not Path(path).exists():
            drop.append(sha)
    for sha in drop:
        del cache["entries"][sha]
    return drop


def invalidate(cache, check_name):
    """Remove a check across all entries. Returns count removed."""
    n = 0
    for sha, entry in cache["entries"].items():
        if check_name in entry.get("checks", {}):
            del entry["checks"][check_name]
            n += 1
    return n


# ============================================================================
# Frontmatter parsing
# ============================================================================

def parse_fm(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]
            except Exception:
                pass
    return {}, text


def word_count(body):
    return len(re.findall(r"\w+", body))


# ============================================================================
# Deterministic checks
# ============================================================================

PAGE_REF_RE = re.compile(r"\(p\.\s*[0-9?]+\)")
WIKILINK_RE = re.compile(r"\[\[([A-Za-z0-9\-_/.]+)\]\]")


def check_source_page(p, fm, body):
    """Return list of {check, pass, severity, details} for a source page."""
    findings = []

    # 1. Required frontmatter fields
    for field in ["title", "authors", "date"]:
        if not fm.get(field):
            findings.append({
                "check": "frontmatter_required",
                "pass": False,
                "severity": "BLOCKING",
                "details": f"missing frontmatter: {field}",
            })

    # 2. study_design empty (only relevant outside theses/notes)
    if "thesis" not in (fm.get("tags") or []) and not fm.get("study_design"):
        findings.append({
            "check": "study_design_empty",
            "pass": False,
            "severity": "WARNING",
            "details": "study_design: not set",
        })

    # 3. DOI missing (theses excused)
    if "thesis" not in (fm.get("tags") or []) and not (fm.get("doi") or "").strip():
        findings.append({
            "check": "doi_missing",
            "pass": False,
            "severity": "WARNING",
            "details": "doi: empty (rerun enrich_frontmatter.py?)",
        })

    # 4. cites: empty (parse_references not run)
    if not fm.get("cites"):
        findings.append({
            "check": "cites_empty",
            "pass": False,
            "severity": "INFO",
            "details": "cites: empty (run parse_references --curate)",
        })

    # 5. cites_unresolved > 5
    unres = fm.get("cites_unresolved") or []
    if len(unres) > 5:
        findings.append({
            "check": "cites_unresolved_high",
            "pass": False,
            "severity": "INFO",
            "details": f"{len(unres)} unresolved citations",
        })

    # 6. Bullets in Findings/Recommendations/Background without page refs
    sections = ["Key Findings", "Recommendations / Implications",
                "Background (from cited literature)", "Primary Outcome",
                "Secondary Outcomes"]
    uncited_total = 0
    for sec in sections:
        m = re.search(rf"^##\s+{re.escape(sec)}\s*$", body, re.MULTILINE)
        if not m:
            continue
        nxt = re.search(r"^##\s+", body[m.end():], re.MULTILINE)
        end = m.end() + nxt.start() if nxt else len(body)
        section_text = body[m.end():end]
        for line in section_text.splitlines():
            if line.strip().startswith("-") and len(line) > 30:
                if not PAGE_REF_RE.search(line):
                    uncited_total += 1
    if uncited_total > 0:
        findings.append({
            "check": "uncited_claims",
            "pass": False,
            "severity": "BLOCKING",
            "details": f"{uncited_total} bullets miss `(p. ?)` in cited sections",
        })

    # 7. Word count vs expected for type
    wc = word_count(body)
    sd = (fm.get("study_design") or "").lower()
    expected_min = {
        "rct": 800, "cohort": 800, "cross-sectional": 800,
        "case-control": 800, "case-series": 600,
        "systematic-review": 1200, "meta-analysis": 1200,
        "scoping-review": 1000, "narrative-review": 800,
        "methodological": 600, "theoretical": 600,
    }.get(sd, 0)
    if expected_min and wc < expected_min * 0.5:
        findings.append({
            "check": "page_too_short",
            "pass": False,
            "severity": "WARNING",
            "details": f"{wc} words (expected ≥ {expected_min} for {sd})",
        })

    # 8. intervention_family set but in wrong folder
    fam = (fm.get("intervention_family") or "").lower()
    if fam and fam != "none":
        path_str = str(p)
        if "/articles/general/" in path_str:
            findings.append({
                "check": "wrong_folder",
                "pass": False,
                "severity": "WARNING",
                "details": f"intervention_family={fam} but file in articles/general/",
            })

    # 9. Extraction Checklist with > 30% unchecked AND no annotation
    cb_section = re.search(r"^##\s+Extraction Checklist\s*$", body, re.MULTILINE)
    if cb_section:
        nxt = re.search(r"^##\s+", body[cb_section.end():], re.MULTILINE)
        end = cb_section.end() + nxt.start() if nxt else len(body)
        cb_text = body[cb_section.end():end]
        unchecked = cb_text.count("- [ ]")
        checked = cb_text.count("- [x]") + cb_text.count("- [X]")
        total = unchecked + checked
        if total > 0 and unchecked / total > 0.3:
            findings.append({
                "check": "checklist_incomplete",
                "pass": False,
                "severity": "BLOCKING",
                "details": f"{unchecked}/{total} checklist items unchecked",
            })

    findings += em_dash_findings(body)

    if not findings:
        findings.append({
            "check": "source_page_overall",
            "pass": True,
            "severity": "INFO",
            "details": "all deterministic checks pass",
        })
    return findings


def check_concept_page(p, fm, body, source_mention_count):
    findings = []
    wc = word_count(body)
    if source_mention_count >= 3 and wc < 500:
        findings.append({
            "check": "concept_stub_priority",
            "pass": False,
            "severity": "WARNING",
            "details": f"{source_mention_count} sources mention this concept "
                       f"but page is {wc} words (stub)",
        })
    findings += em_dash_findings(body)
    return findings


def check_method_page(p, fm, body):
    findings = []
    used_in = re.search(r"^##\s+Used In This Wiki\s*$", body, re.MULTILINE)
    if used_in:
        nxt = re.search(r"^##\s+", body[used_in.end():], re.MULTILINE)
        end = used_in.end() + nxt.start() if nxt else len(body)
        used_text = body[used_in.end():end]
        bare_links = 0
        described = 0
        for line in used_text.splitlines():
            if line.strip().startswith("- [["):
                # Check if line has more than just a wikilink (a description)
                if len(line.strip()) < 40:
                    bare_links += 1
                else:
                    described += 1
        if bare_links > 0:
            findings.append({
                "check": "method_bare_wikilinks",
                "pass": False,
                "severity": "WARNING",
                "details": f"{bare_links} bare wikilinks in `## Used In This Wiki` "
                           f"(no per-source description)",
            })
    findings += em_dash_findings(body)
    return findings


def all_source_pages():
    if not SRC_DIR.is_dir():
        return []
    out = []
    for p in sorted(SRC_DIR.rglob("*.md")):
        if p.name in {"index.md", "log.md", "overview.md"}:
            continue
        text = p.read_text(encoding="utf-8")
        fm, body = parse_fm(text)
        out.append((p, fm, body))
    return out


def run_deterministic_checks(only_paths=None, severity_filter=None):
    findings = []
    sources = all_source_pages()
    src_index = {p.stem: (p, fm, body) for p, fm, body in sources}

    # Source page checks
    for p, fm, body in sources:
        if only_paths and not any(str(p).startswith(str(op)) for op in only_paths):
            continue
        for f in check_source_page(p, fm, body):
            f["file"] = str(p.relative_to(REPO_ROOT))
            findings.append(f)

    # Concept page checks (need to count source mentions per concept)
    concepts_dir = WIKI_DIR / "concepts"
    if concepts_dir.is_dir():
        for cp in sorted(concepts_dir.glob("*.md")):
            if only_paths and not any(str(cp).startswith(str(op)) for op in only_paths):
                continue
            text = cp.read_text(encoding="utf-8")
            fm, body = parse_fm(text)
            token = f"[[{cp.stem}]]"
            mentions = sum(1 for _, _, b in sources if token in b)
            for f in check_concept_page(cp, fm, body, mentions):
                f["file"] = str(cp.relative_to(REPO_ROOT))
                findings.append(f)

    # Method page checks
    methods_dir = WIKI_DIR / "methods"
    if methods_dir.is_dir():
        for mp in sorted(methods_dir.glob("*.md")):
            if only_paths and not any(str(mp).startswith(str(op)) for op in only_paths):
                continue
            text = mp.read_text(encoding="utf-8")
            fm, body = parse_fm(text)
            for f in check_method_page(mp, fm, body):
                f["file"] = str(mp.relative_to(REPO_ROOT))
                findings.append(f)

    if severity_filter:
        target = severity_filter.upper()
        findings = [f for f in findings if f.get("severity") == target]
    return findings


# ============================================================================
# CLI
# ============================================================================

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    chk = sub.add_parser("check", help="Run deterministic checks")
    chk.add_argument("--paths", nargs="+", help="Limit to these wiki paths")
    chk.add_argument("--severity", choices=["BLOCKING", "WARNING", "INFO"],
                     help="Filter by severity")

    cache = sub.add_parser("cache", help="Cache management")
    cache.add_argument("--status", action="store_true")
    cache.add_argument("--gc", action="store_true")
    cache.add_argument("--invalidate", help="Invalidate a check name across all entries")

    args = ap.parse_args()

    if args.cmd == "check":
        only_paths = [Path(p).resolve() for p in (args.paths or [])]
        results = run_deterministic_checks(
            only_paths=only_paths,
            severity_filter=args.severity,
        )
        # Group by severity
        out = {"BLOCKING": [], "WARNING": [], "INFO": []}
        for r in results:
            out.setdefault(r["severity"], []).append(r)
        out["summary"] = {
            "total": len(results),
            "blocking": len(out["BLOCKING"]),
            "warning": len(out["WARNING"]),
            "info": len(out["INFO"]),
            "agent_version": CURRENT_AGENT_VERSION,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    if args.cmd == "cache":
        c = load_cache()
        if args.status:
            print(json.dumps({
                "agent_version": c.get("agent_version"),
                "entries": len(c.get("entries", {})),
                "cache_file": str(CACHE_FILE),
            }, indent=2))
            return
        if args.gc:
            removed = gc_cache(c)
            save_cache(c)
            print(f"Removed {len(removed)} stale entries.")
            return
        if args.invalidate:
            n = invalidate(c, args.invalidate)
            save_cache(c)
            print(f"Invalidated `{args.invalidate}` across {n} entries.")
            return
        print("No cache subcommand. Try --status, --gc, or --invalidate <name>.")


if __name__ == "__main__":
    main()
