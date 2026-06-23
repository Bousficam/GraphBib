# Standalone Tools

Reference for the Python helpers that complement the agent. These are
pure scripts — no LLM call unless explicitly noted — and the agent
runs them on user request.

## Domain configuration

GraphBib ships **domain-neutral**. The analyzer tools that need a
field-specific vocabulary read it from a single machine-readable file,
`tools/data/domain.json`, which mirrors the prose taxonomy you declare
in `context.md`. The shipped `domain.json` is the **neutral baseline**
(every section empty), so a fresh clone is not pre-configured for any
field.

Sections:

| Section | Shape | Consumed by |
|---|---|---|
| `regions`, `tracts` | `{key: {canonical, aliases:[plain strings]}}` | `brain_atlas_anchor.py`, `dti_aggregator.py` (tract context) |
| `dti_metrics` | `{CANON: [aliases]}` | `dti_aggregator.py` |
| `outcome_scales` | `{KEY: [regex fragments]}` | `effect_size_aggregator.py` |
| `cohort.{chronicity,side,lesion}` | `{category: [regex fragments]}` | `cohort_tracker.py` |
| `cohort.severity_scale` | `{name, regex}` (2 capture groups = range) | `cohort_tracker.py` |

Convention: `regions` / `tracts` aliases are **plain strings** (the
tools escape them and match on word boundaries); the `dti_metrics` /
`outcome_scales` / `cohort.*` values are **regex fragments**, OR-joined
raw (so numeric patterns like `>\s*6\s*month` work).

To configure a domain:

```bash
# activate a ready-made pack…
cp tools/data/domain.stroke.example.json tools/data/domain.json
# …or edit tools/data/domain.json directly.
```

These four tools are **domain-specific**: with the empty default they
print a "configure your domain" hint and exit (except `cohort_tracker`,
which still reports pooled sample sizes from frontmatter). They only do
domain work once `domain.json` is filled. `tools/organize_sources.py`
keeps its own taxonomy mirror (`FAMILY_FOLDER` / `IMAGING_METHODS`) in
Python, with a safe fallback to `articles/general/` for unknown
families.

## Concept consolidation (batched)

`tools/consolidate_concepts.py` batches concept-page extension: one
LLM call per concept, prompt-cached, integrating all pending sources
that touched that concept since its last update. ~70 % cheaper than
per-ingest extension on homogeneous corpora.

```bash
python tools/consolidate_concepts.py --report   # pending counts
python tools/consolidate_concepts.py <Concept>  # one
python tools/consolidate_concepts.py --since 7d
```

When run periodically, ingest step 8 (concept extension) may defer to
the batched run.

## Replication tracking

Each Academic Paper template includes a `replication_of: "<DOI>"`
frontmatter field — filled at ingest when the paper explicitly
replicates a prior study. `tools/replication_tracker.py` walks
`wiki/sources/`, follows the chains, and reports:

- **Replication chains** — original → replication(s), with consistent
  vs inconsistent findings flagged.
- **Single-study claims** — concept pages whose `## Empirical Evidence`
  rests on one source (a flag for confidence).
- **Replication candidates** — papers that could plausibly replicate
  an existing finding but don't claim it explicitly.

Run periodically; complements `/wiki-lint`.

## Audit trail (git as history)

The wiki is a git repo — `git log` and `git blame` already provide a
free audit trail. Every ingestion appends to `wiki/log.md` with
`## [YYYY-MM-DD] ingest | <Title>`, and each commit touches the wiki
pages the source affected.

`tools/audit_page.py <wiki-page>` wraps `git blame` to map each line
to the ingest commit that introduced it. Useful for:

- Defending a claim during a thesis review.
- Identifying when a concept's definition shifted.
- Untangling synthesis lines that reference multiple sources.
