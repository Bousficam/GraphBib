---
description: End-to-end reading discovery — suggest-reading → fetch-reading → conversion → ingest, with user confirmation between phases.
argument-hint: "[<ConceptName> | --all]"
---

Discover, fetch, convert, and ingest new readings from outside the
wiki. Chains the discovery sub-agents with confirmation gates.

Arguments: $ARGUMENTS

- If a concept name is provided (e.g. `MotorImagery`), the discovery
  is focused on that concept.
- `--all` (or no argument) runs a wiki-wide pass.

# Procedure

## Phase 1 — Suggest readings

Delegate to the `suggest-reading` sub-agent:

```
Agent(subagent_type=suggest-reading, prompt="<scope from $ARGUMENTS>")
```

The sub-agent runs:
- Internal snowball (DOIs cited 2+ times across the wiki).
- OpenAlex forward citations (papers citing the wiki, ranked by
  co-citation × velocity × venue h-index).

Output: tiered reading list (Tier 1 / Tier 2 / Tier 3) with rationale.

Surface the list to the user and ask: *"Which tiers should I fetch?
[1] / [1+2] / [all] / [skip]"*. Wait for choice.

## Phase 2 — Fetch open-access PDFs

If the user picked tiers, extract the DOIs and delegate to
`fetch-reading`:

```
Agent(subagent_type=fetch-reading,
      prompt="Fetch these DOIs into raw/<vault>/papers/: <list>")
```

The sub-agent calls Unpaywall, downloads OA PDFs, surfaces paywalled
ones for manual fetch. Reports per-DOI status.

If the user skipped Phase 2, stop and tell them to fetch manually
when ready.

## Phase 3 — Convert (optional, opt-in)

If new PDFs are downloaded, ask: *"Run the conversion pipeline now?
[Y/n]"*. If yes:

```bash
python pdf2md/pdf2md_marker.py raw/<vault>/papers raw/<vault>/papers
python pdf2md/pdf2md_fallback.py raw/<vault>/papers raw/<vault>/papers
python pdf2md/enrich_frontmatter.py raw/<vault>/papers
python tools/parse_references.py --curate --all raw/<vault>/papers
```

(Optionally include Mistral OCR if marker had failures and the user
has `MISTRAL_API_KEY`.)

If the user skipped, tell them to run `/wiki-convert` later.

## Phase 4 — Ingest (opt-in)

If the conversion produced new MDs, ask: *"Ingest the new sources
now? [Y/n]"*. If yes:

Delegate to `/wiki-batch-ingest`:

```
/wiki-batch-ingest raw/<vault>/papers/
```

This loops over the new sources via the `ingester` sub-agent, with
batch confirmation.

If the user skipped, tell them to run `/wiki-batch-ingest` later.

## Phase 5 — Recap

```
=== Discovery session — <date> ===

Scope: <concept | wiki-wide>

Phase 1 (suggest-reading):
  - Internal snowball: <N> candidates
  - OpenAlex forward: <M> candidates
  - Tier 1 / 2 / 3: <a> / <b> / <c>

Phase 2 (fetch-reading):
  - Downloaded: <N>
  - Paywalled (manual fetch): <M> — see report
  - Errors: <K>

Phase 3 (conversion):
  - Marker: <ok> ok, <suspicious> suspicious, <errors> errors
  - Fallback rescued: <N>
  - Enrich: <crossref_ok> with metadata

Phase 4 (ingest):
  - Sources ingested: <N>
  - Concepts touched: <list>
  - Methods touched: <list>
  - Recommendations created: <count>

Suggested follow-ups:
  - python tools/update_cited_by.py
  - python tools/consolidate_concepts.py --since 1d
  - Agent(subagent_type=concept-builder, prompt="<concept>") for any
    concept that gained 3+ sources from this discovery batch.
```

# Failure handling

- If `suggest-reading` returns 0 candidates: tell the user the wiki
  has no relevant snowball or forward-citation gaps for that scope.
- If `fetch-reading` reports many paywalled DOIs (>50 % of selection):
  surface the institutional-fetch list and skip the conversion phase.
- If `pdf2md_marker` errors on most files (rare): suggest invoking
  Mistral phase from `/wiki-convert`.
- Each phase is independent: a failure stops the chain, the user can
  resume from the next phase manually later.

# Notes

- Each sub-agent has its own context window — the parent (you) stays
  light, only orchestrating.
- Phases 3 and 4 are confirmable independently, so the user can pause
  for review (e.g. inspect downloaded PDFs before triggering the
  conversion).
- Repeated `/wiki-discover` runs are nearly free for the discovery
  step (OpenAlex cache).
