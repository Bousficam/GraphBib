---
description: Forward-citation snowball from one specific source - find recent papers that cite it and rank by impact.
argument-hint: "<source-slug>"
---

Explore the descendants of one paper - what's been published recently
that builds on this work?

Arguments: $ARGUMENTS - the source slug to snowball forward from
(e.g. `lefaucheur-2014`, `cervera-2020`).

# Procedure

Delegate to the `suggest-reading` sub-agent in focused-source mode:

```
Agent(subagent_type=suggest-reading,
      prompt="Forward-citation snowball from $ARGUMENTS. Use OpenAlex,
              return tier-1 candidates ranked by velocity × venue h-index,
              with rationale per candidate.")
```

The sub-agent:
- Resolves the source's DOI from its frontmatter.
- Calls OpenAlex `/works/<id>/cited_by_api_url` to list papers
  citing this source, sorted by `cited_by_count` DESC.
- Filters: passes if velocity ≥ 2.5 AND venue h-index ≥ 30 (high-
  impact recent papers only - for one-source forward, co-citation
  isn't applicable since we're not aggregating).
- Returns a tiered list (Tier 1 / Tier 2 / Tier 3).

# Notes

- Differs from `/wiki-discover` (which scans wiki-wide and aggregates
  co-citations across all sources). Use this when you specifically
  want to track ONE seminal paper's intellectual descendants.
- Common use case: after ingesting a major guideline (Lefaucheur,
  Cervera meta-analysis, etc.), run `/wiki-snowball <slug>` to find
  what's been published since that builds on it.
- For fetch-then-ingest, follow up with `/wiki-discover` (which can
  reuse the same OpenAlex cache) or invoke `fetch-reading` directly
  on the Tier 1 DOIs.
