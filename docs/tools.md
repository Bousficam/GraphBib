# Standalone Tools

Reference for the Python helpers that complement the agent. These are
pure scripts — no LLM call unless explicitly noted — and the agent
runs them on user request.

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
