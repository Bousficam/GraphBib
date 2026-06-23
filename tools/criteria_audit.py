#!/usr/bin/env python3
"""Audit a screening/criteria.md for common defects before screening starts.

Catches deterministic problems that would cause biased exclusions or
disagreement between screeners on the same article:

  1. **PICO completeness** - every PICO row has a non-placeholder
     definition (no `<from Q1>` style stubs left behind).
  2. **Stage tag presence** - every criterion row has a Stage cell
     ∈ {tiab, fulltext, both}. Missing or unknown values are flagged
     so the screener-tiab agent's testability gate can fire.
  3. **Tag uniqueness** - every criterion `tag` appears once. Two
     rows with the same tag would collide in the decisions CSV.
  4. **Vague terms** - criterion text contains weasel words that
     two screeners would interpret differently ("recent", "elderly",
     "severe", "high-quality"…). Listed in VAGUE_TERMS below.
  5. **Untestable / subjective phrasing** - criterion contains
     value-laden judgements ("good quality", "appropriate",
     "adequate") that PRISMA forbids from the eligibility bar.
  6. **Missing 'Verifiable from' column** on the exclusion table - 
     the column tells the screener where to look in the body; its
     absence is allowed but flagged as a hygiene warning.

The audit is purely textual - no LLM, no network. It surfaces
findings; the user (or a follow-up LLM pass via the
`/extractor-screen-validate-criteria` slash command) decides how
to resolve each.

Output:
    screening/reports/criteria-audit.md   (markdown with one section
                                            per finding category)

Exit code 0 always - findings are informational, not a hard
failure (the screening can still run on a flawed criteria.md, just
with the expected biases).

Usage:
    python tools/criteria_audit.py project-review/<vault>/<name>
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# ----------------------------------------------------------------------
# Lexicons (domain-neutral - describe LANGUAGE issues, not domain content)

# Weasel words that need quantification. Pure language-level - same
# word is vague in any domain.
VAGUE_TERMS = {
    "recent", "current", "modern", "novel", "new", "old",
    "elderly", "young", "adult",  # without an explicit age range
    "small", "large", "big", "tiny",
    "severe", "moderate", "mild",   # without explicit grade
    "high", "low", "medium",        # without explicit numeric threshold
    "significant", "important", "relevant", "meaningful",
    "appropriate", "adequate", "reasonable", "sufficient",
    "good", "bad", "poor",
    "quality", "high-quality", "well-designed",
    "soon", "shortly", "early", "late",
    "few", "several", "many", "some",
    "robust", "valid",                # without "validated against X"
    "appropriate", "feasible",
}

# Subjective / value-laden phrases - explicit forbidden in PRISMA
# eligibility criteria (they introduce screener-level disagreement).
SUBJECTIVE_PHRASES = [
    "high quality", "high-quality",
    "low quality", "low-quality",
    "well designed", "well-designed",
    "good methodology", "poor methodology",
    "appropriate sample", "adequate sample",
    "sufficiently powered", "adequately powered",
    "convincing", "rigorous", "credible",
    "as appropriate", "as needed", "where applicable",
]

# Tokens that mean a placeholder was left in the template
PLACEHOLDER_PATTERNS = [
    re.compile(r"<from\s+Q\d+[a-z]?\s*[\u2014\u2013-]?[^>]*>", re.I),
    re.compile(r"<verbatim[^>]*>", re.I),
    re.compile(r"<derived[^>]*>", re.I),
    re.compile(r"<e\.g\.[^>]*>", re.I),
    re.compile(r"<if applicable[^>]*>", re.I),
    re.compile(r"<short text>", re.I),
    re.compile(r"<tag>", re.I),
]

VALID_STAGES = {"tiab", "fulltext", "both"}


# ----------------------------------------------------------------------
# Markdown parsing

def find_section(md, header):
    """Return the body of `## header` until the next `## ` or EOF, or ""."""
    pat = re.compile(rf"^##\s+{re.escape(header)}\s*$", re.M)
    m = pat.search(md)
    if not m:
        return ""
    nxt = re.search(r"^##\s+", md[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(md)
    return md[m.end():end].strip()


def parse_table(section_text):
    """Parse a simple markdown pipe-table. Returns (headers, [row dicts])."""
    lines = [ln for ln in section_text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return [], []
    # Header row + separator + data rows
    headers = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    rows = []
    for raw in lines[2:]:
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        # Pad / trim to header length
        if len(cells) < len(headers):
            cells = cells + [""] * (len(headers) - len(cells))
        else:
            cells = cells[:len(headers)]
        rows.append(dict(zip(headers, cells)))
    return headers, rows


def parse_criteria_md(text):
    """Extract PICO + inclusion + exclusion tables from the criteria.md text.

    Returns dict with:
      pico         : [{Element, Definition}]
      inclusion    : [{Tag, Stage?, Criterion}]
      exclusion    : [{#, Tag, Stage?, Criterion, Verifiable from?}]
      notes        : raw text under "Notes for the screener sub-agents"
      decisions    : raw text under "Pre-screening decisions (audit)"
    """
    out = {}
    _, out["pico"] = parse_table(find_section(text, "PICO"))
    _, out["inclusion"] = parse_table(find_section(text, "Inclusion criteria"))
    out["exclusion_headers"], out["exclusion"] = parse_table(
        find_section(text, "Exclusion criteria")
    )
    out["notes"] = find_section(text, "Notes for the screener sub-agents")
    out["decisions"] = find_section(text, "Pre-screening decisions (audit)")
    return out


# ----------------------------------------------------------------------
# Checks

def check_pico(pico):
    """Each PICO row needs a non-placeholder Definition."""
    findings = []
    if not pico:
        findings.append({
            "level": "error",
            "rule": "pico-missing",
            "message": "No PICO table found. The criteria.md must declare "
                       "Population / Intervention / Comparator / Outcome.",
        })
        return findings
    for row in pico:
        element = row.get("Element") or ""
        defn = row.get("Definition") or ""
        if not defn.strip() or _has_placeholder(defn):
            findings.append({
                "level": "error",
                "rule": "pico-placeholder",
                "message": f"PICO row **{element}** still contains a "
                           f"placeholder or is empty: `{defn[:80]}`",
            })
    return findings


def check_stage_tags(rows, label):
    """Every criterion row needs a Stage ∈ {tiab, fulltext, both}."""
    findings = []
    has_stage_column = bool(rows) and "Stage" in rows[0]
    if not has_stage_column:
        findings.append({
            "level": "warn",
            "rule": "stage-column-missing",
            "message": f"{label} table has no `Stage` column. The "
                       f"screener-tiab will treat every criterion as `both` "
                       f"(safest fallback). Re-run /extractor-screen-init "
                       f"Q9 to tag each criterion explicitly.",
        })
        return findings
    for row in rows:
        tag = row.get("Tag") or "?"
        stage = (row.get("Stage") or "").strip().lower()
        if not stage or _has_placeholder(stage):
            findings.append({
                "level": "error",
                "rule": "stage-missing",
                "message": f"{label} criterion `{tag}` has no Stage value. "
                           f"Set it to `tiab`, `fulltext`, or `both` "
                           f"(see Q9).",
            })
        elif stage not in VALID_STAGES:
            findings.append({
                "level": "error",
                "rule": "stage-invalid",
                "message": f"{label} criterion `{tag}` has Stage="
                           f"`{stage}` (must be one of {sorted(VALID_STAGES)}).",
            })
    return findings


def check_tag_uniqueness(rows, label):
    """Two rows with the same Tag would collide in tiab-decisions.csv."""
    findings = []
    seen = {}
    for i, row in enumerate(rows, start=1):
        tag = (row.get("Tag") or "").strip()
        if not tag or _has_placeholder(tag):
            findings.append({
                "level": "error",
                "rule": "tag-missing",
                "message": f"{label} row {i} has no Tag (or a placeholder).",
            })
            continue
        if tag in seen:
            findings.append({
                "level": "error",
                "rule": "tag-duplicate",
                "message": f"{label} tag `{tag}` appears in two rows "
                           f"({seen[tag]} and {i}). Tags must be unique.",
            })
        else:
            seen[tag] = i
    return findings


def check_criterion_text(rows, label):
    """Vague terms + subjective phrasing + placeholders in the criterion text."""
    findings = []
    for row in rows:
        tag = (row.get("Tag") or "?").strip()
        text = row.get("Criterion") or ""
        if not text.strip():
            findings.append({
                "level": "error",
                "rule": "criterion-empty",
                "message": f"{label} criterion `{tag}` has no body text.",
            })
            continue
        if _has_placeholder(text):
            findings.append({
                "level": "error",
                "rule": "criterion-placeholder",
                "message": f"{label} criterion `{tag}` still contains a "
                           f"template placeholder: `{text[:80]}`",
            })
            continue
        # Vague terms (case-insensitive, whole-word match)
        for w in VAGUE_TERMS:
            if re.search(rf"\b{re.escape(w)}\b", text, re.I):
                findings.append({
                    "level": "warn",
                    "rule": "vague-term",
                    "message": f"{label} criterion `{tag}` uses vague "
                               f"term `{w}` without quantification. "
                               f"Two screeners may interpret it "
                               f"differently. (Text: \"{text[:120]}\")",
                })
                break  # one vague-term flag per row
        # Subjective phrasing (substring match - phrases include spaces)
        for phrase in SUBJECTIVE_PHRASES:
            if phrase.lower() in text.lower():
                findings.append({
                    "level": "warn",
                    "rule": "subjective-phrase",
                    "message": f"{label} criterion `{tag}` uses subjective "
                               f"phrasing `{phrase}`. PRISMA discourages "
                               f"value-laden language at the eligibility "
                               f"bar - these should be quality-appraisal "
                               f"items, not screening criteria.",
                })
                break
    return findings


def check_verifiable_column(exclusion_headers):
    """Exclusion table SHOULD have a Verifiable-from column (where to look)."""
    if exclusion_headers and "Verifiable from" not in exclusion_headers:
        return [{
            "level": "info",
            "rule": "verifiable-missing",
            "message": "Exclusion table has no `Verifiable from` column. "
                       "Adding it (e.g. \"Methods §Participants\", "
                       "\"metadata / first page\") helps the "
                       "screener-fulltext locate the evidence quickly.",
        }]
    return []


def _has_placeholder(s):
    return any(p.search(s) for p in PLACEHOLDER_PATTERNS)


# ----------------------------------------------------------------------
# Output

def render_report(findings, criteria_path, project):
    by_level = {"error": [], "warn": [], "info": []}
    for f in findings:
        by_level.setdefault(f["level"], []).append(f)

    lines = [
        "# Criteria audit",
        "",
        f"Source : `{criteria_path.relative_to(project.parent)}`",
        "",
        f"- **ERRORS**: {len(by_level['error'])} - these will cause biased "
        "exclusions or screener crashes; fix before running screening.",
        f"- **WARNINGS**: {len(by_level['warn'])} - language likely to "
        "produce disagreement between screeners; clarify.",
        f"- **INFO**: {len(by_level['info'])} - hygiene suggestions.",
        "",
        "Re-run `/extractor-screen-validate-criteria <project>` after "
        "editing `criteria.md` to confirm the audit is clean.",
        "",
    ]
    if not findings:
        lines.append("**✓ No issues detected.** The criteria.md is "
                     "audit-clean.")
        lines.append("")
    else:
        for level in ("error", "warn", "info"):
            if not by_level[level]:
                continue
            lines.append(f"## {level.upper()}")
            lines.append("")
            for f in by_level[level]:
                lines.append(f"- **[{f['rule']}]** {f['message']}")
            lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("project", help="Path to project-review/<vault>/<name>/")
    ap.add_argument("--json", action="store_true",
                    help="Emit findings as JSON on stdout (machine-readable).")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    criteria = project / "screening" / "criteria.md"
    if not criteria.exists():
        sys.exit(f"error: {criteria} not found. Run /extractor-screen-init first.")

    text = criteria.read_text(encoding="utf-8")
    if not text.strip():
        sys.exit(f"error: {criteria} is empty.")

    data = parse_criteria_md(text)

    findings = []
    findings.extend(check_pico(data["pico"]))
    findings.extend(check_stage_tags(data["inclusion"], "Inclusion"))
    findings.extend(check_stage_tags(data["exclusion"], "Exclusion"))
    findings.extend(check_tag_uniqueness(data["inclusion"], "Inclusion"))
    findings.extend(check_tag_uniqueness(data["exclusion"], "Exclusion"))
    findings.extend(check_criterion_text(data["inclusion"], "Inclusion"))
    findings.extend(check_criterion_text(data["exclusion"], "Exclusion"))
    findings.extend(check_verifiable_column(data.get("exclusion_headers", [])))

    if args.json:
        import json
        print(json.dumps(findings, indent=2, ensure_ascii=False))
        return

    report = render_report(findings, criteria, project)
    out_path = project / "screening" / "reports" / "criteria-audit.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    n_err = sum(1 for f in findings if f["level"] == "error")
    n_warn = sum(1 for f in findings if f["level"] == "warn")
    n_info = sum(1 for f in findings if f["level"] == "info")
    print(f"✓ Audited {criteria.relative_to(project.parent)}")
    print(f"  PICO rows      : {len(data['pico'])}")
    print(f"  Inclusion rows : {len(data['inclusion'])}")
    print(f"  Exclusion rows : {len(data['exclusion'])}")
    print()
    print(f"  ERRORS : {n_err}")
    print(f"  WARN   : {n_warn}")
    print(f"  INFO   : {n_info}")
    print()
    print(f"✓ Report : {out_path.relative_to(project.parent)}")


if __name__ == "__main__":
    main()
