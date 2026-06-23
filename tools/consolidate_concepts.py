#!/usr/bin/env python3
"""Batched concept consolidation - extend concept pages from accumulated
sources, periodically rather than per-ingest.

Rationale
=========

Per-ingest concept extension makes Claude re-read the concept page on
EVERY new source that touches it (~5-10 k tokens per concept × N
concepts × M ingests). For a homogeneous corpus (50 MI-BCI papers),
this dominates the ingestion cost without proportional quality gain
 - the page is rebuilt 50 times.

Alternative workflow (this tool):
  1. During routine ingest, the agent skips deep concept extension and
     instead appends a brief "Pending Claims" entry to the source page
     (or to a shared queue file).
  2. Periodically (every N ingestions, or on user request via
     /wiki-consolidate-concepts), this tool walks each concept page,
     gathers all sources tagged with it that have NOT yet been folded
     in, and produces ONE batched LLM call per concept that integrates
     them all.

Cost comparison (50 papers × 5 concepts each):
  - Per-ingest: 50 × 5 × ~8k = 2 M tokens of concept-page reads/writes.
  - Batched (every 10 ingests, with caching): 5 × 10 batches × 8k
    + 5 × 10 batches × 5×4k cached = ~600k effective tokens.
  → ~70% reduction with quality preserved (the LLM sees more context
  per call, so synthesis is actually cleaner).

Modes
=====

    # Inventory - list which concepts have unconsolidated sources
    python tools/consolidate_concepts.py --report

    # Consolidate one concept (re-reads ALL its sources)
    python tools/consolidate_concepts.py MotorImagery

    # Consolidate every concept page touched by sources ingested in
    # the last 7 days (uses git log on wiki/sources/)
    python tools/consolidate_concepts.py --since 7d

    # Consolidate everything (full re-synthesis, expensive)
    python tools/consolidate_concepts.py --all

The tool calls Claude (via litellm) with prompt caching on the
existing concept page + the relevant section of each source.
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, SRC_DIR, WIKI_DIR, WIKILINK_RE, load_sources, parse_fm  # noqa: E402

CONCEPTS_DIR = WIKI_DIR / "concepts"
DEFAULT_LLM_MODEL = "claude-sonnet-4-6"  # synthesis tier - quality matters
LLM_MAX_TOKENS = 6000
LLM_SLEEP_SEC = 0.1


def list_concept_pages():
    if not CONCEPTS_DIR.is_dir():
        return []
    return sorted(CONCEPTS_DIR.glob("*.md"))


def sources_for_concept(concept_slug, sources):
    """Sources that wikilink to [[concept_slug]] in their body."""
    token = f"[[{concept_slug}]]"
    return [s for s in sources if token in s["body"]]


def already_cited_in_concept(concept_text, source_slug):
    return f"[[{source_slug}]]" in concept_text


def report(sources):
    print("Concept page         | sources | already-cited | pending consolidation")
    print("-" * 82)
    pages = list_concept_pages()
    if not pages:
        print("(no concept pages)")
        return
    for p in pages:
        text = p.read_text(encoding="utf-8")
        related = sources_for_concept(p.stem, sources)
        already = sum(1 for s in related if already_cited_in_concept(text, s["slug"]))
        pending = len(related) - already
        flag = " ⚠" if pending >= 3 else ""
        print(f"{p.stem:<20} | {len(related):>7} | {already:>13} | {pending:>20}{flag}")


def section(body, header):
    pat = re.compile(rf"^##\s+{re.escape(header)}\s*$", re.MULTILINE)
    m = pat.search(body)
    if not m:
        return ""
    nxt = re.search(r"^##\s+", body[m.end():], re.MULTILINE)
    end = m.end() + nxt.start() if nxt else len(body)
    return body[m.end():end].strip()


def llm_consolidate(concept_text, concept_slug, source_blobs, dry_run):
    """One LLM call that takes a concept page + N source excerpts and
    returns an updated concept page integrating them.
    """
    if dry_run:
        return concept_text + f"\n\n<!-- [dry-run] would integrate {len(source_blobs)} sources -->\n"

    try:
        from litellm import completion
    except ImportError:
        sys.exit("litellm not installed. Run: pip install litellm")

    sources_block = "\n\n".join(
        f"### Source: [[{s['slug']}]]\n{s['excerpt']}"
        for s in source_blobs
    )

    system_block = (
        "You maintain academic concept pages (1500-3500 word chapter-style).\n"
        "Each concept page is enriched incrementally as new sources touch it.\n\n"
        "Rules:\n"
        "- Apply the Indirect Citation Rule strictly: each new claim cites the\n"
        "  ORIGINATING paper, with `reported via` provenance when relevant.\n"
        "- For each new source, identify what it contributes (new sub-claim,\n"
        "  variant of definition, framework, mechanism, or measurement) and\n"
        "  append it to the appropriate section.\n"
        "- DO NOT remove existing content. Only add or refine.\n"
        "- Preserve frontmatter (`title:`, `type:`, `aka:`, `domain:`, etc.).\n"
        "- Update the `last_updated:` field to today's date.\n"
        "- Append all new source slugs to `sources:` if not already there.\n"
        "- Output the COMPLETE updated concept page (frontmatter + body).\n"
    )

    user_block = (
        f"Concept page: [[{concept_slug}]]\n\n"
        f"Current concept page content:\n---\n{concept_text}\n---\n\n"
        f"New sources to integrate ({len(source_blobs)} sources):\n\n"
        f"{sources_block}\n\n"
        "Return the COMPLETE updated concept page below, integrating each "
        "new source's contribution into the appropriate section. Apply the "
        "Indirect Citation Rule. Update last_updated and sources."
    )

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": system_block,
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": user_block},
            ],
        }
    ]

    model = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
    try:
        resp = completion(
            model=model,
            messages=messages,
            max_tokens=LLM_MAX_TOKENS,
        )
        time.sleep(LLM_SLEEP_SEC)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"<llm-error: {type(e).__name__}: {e}>"


def consolidate_concept(concept_path, sources, dry_run):
    text = concept_path.read_text(encoding="utf-8")
    concept_slug = concept_path.stem
    related = sources_for_concept(concept_slug, sources)
    pending = [s for s in related if not already_cited_in_concept(text, s["slug"])]
    if not pending:
        print(f"  · {concept_slug}: nothing to consolidate")
        return

    # Build a compact excerpt per source: Background + Results bullets
    blobs = []
    for s in pending[:20]:  # cap to 20 to keep token cost bounded
        bg = section(s["body"], "Background (from cited literature)") or section(s["body"], "Summary")
        results = section(s["body"], "Results (this paper's findings)") or section(s["body"], "Key Findings")
        excerpt = f"**Background**:\n{bg[:1500]}\n\n**Results**:\n{results[:1500]}"
        blobs.append({"slug": s["slug"], "excerpt": excerpt})

    print(f"  · {concept_slug}: integrating {len(blobs)} new source(s)…")
    new_text = llm_consolidate(text, concept_slug, blobs, dry_run)
    if new_text.startswith("<llm-error"):
        print(f"  ✗ {concept_slug}: {new_text}", file=sys.stderr)
        return

    if dry_run:
        print(f"  [dry] would rewrite {concept_path}")
    else:
        concept_path.write_text(new_text + ("" if new_text.endswith("\n") else "\n"), encoding="utf-8")
        print(f"  ✓ {concept_slug}: updated ({len(blobs)} sources integrated)")


def filter_recent_concepts(sources, since_arg):
    """Use git log to find sources touched within `since_arg` (e.g. '7d').

    Returns the set of concept slugs those sources reference.
    """
    sources_rel = SRC_DIR.relative_to(REPO_ROOT).as_posix() + "/"
    try:
        out = subprocess.check_output(
            ["git", "log", f"--since={since_arg}", "--name-only", "--pretty=format:",
             "--", sources_rel],
            cwd=REPO_ROOT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None

    recent_slugs = set()
    for line in out.splitlines():
        line = line.strip()
        if line.endswith(".md") and sources_rel in line:
            recent_slugs.add(Path(line).stem)
    if not recent_slugs:
        return set()

    concepts = set()
    for s in sources:
        if s["slug"] in recent_slugs:
            for slug in WIKILINK_RE.findall(s["body"]):
                # Only keep if a corresponding concept page exists
                if (CONCEPTS_DIR / f"{slug}.md").is_file():
                    concepts.add(slug)
    return concepts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("concept", nargs="?", help="Concept name (slug, e.g. MotorImagery)")
    ap.add_argument("--all", action="store_true", help="Consolidate every concept page")
    ap.add_argument("--since", help="Only consolidate concepts touched by sources from the last N days (e.g. '7d')")
    ap.add_argument("--report", action="store_true", help="List pending consolidations and exit")
    ap.add_argument("--dry-run", action="store_true", help="Don't write changes")
    args = ap.parse_args()

    sources = load_sources()
    if not sources:
        sys.exit("No sources in wiki/sources/")

    if args.report:
        report(sources)
        return

    if args.all:
        targets = list_concept_pages()
    elif args.since:
        slugs = filter_recent_concepts(sources, args.since)
        if slugs is None:
            sys.exit("git log failed - are you in a git repo?")
        targets = [CONCEPTS_DIR / f"{s}.md" for s in sorted(slugs)
                   if (CONCEPTS_DIR / f"{s}.md").is_file()]
        if not targets:
            print(f"No concept pages need consolidation in the last {args.since}.")
            return
    elif args.concept:
        path = CONCEPTS_DIR / f"{args.concept}.md"
        if not path.is_file():
            sys.exit(f"Concept page not found: {path}")
        targets = [path]
    else:
        ap.error("Provide a concept name, --all, --since, or --report.")

    print(f"Consolidating {len(targets)} concept page(s)…")
    for t in targets:
        consolidate_concept(t, sources, args.dry_run)


if __name__ == "__main__":
    main()
