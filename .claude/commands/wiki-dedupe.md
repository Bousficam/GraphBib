---
description: Find and resolve redundant concept / method / intervention pages - runs the deterministic pre-filter, then delegates to the deduplicator sub-agent.
argument-hint: "[--kind concepts|methods|interventions] [--min-score 0.35] [--top N]"
---

Run the deduplication workflow on the wiki.

Arguments: $ARGUMENTS

# Procedure

## Step 1 - Deterministic pre-filter (no LLM tokens)

```bash
python tools/find_redundancy.py $ARGUMENTS
```

This emits `tools/.cache/redundancy_candidates.json` and a human
summary on stdout. Default behaviour scans `wiki/concepts/`,
`wiki/methods/`, and `wiki/interventions/`, surfacing pairs whose
combined similarity score exceeds the threshold or whose individual
signals (title overlap, alias match, co-citation, tag Jaccard,
text overlap) cross per-signal thresholds.

Common overrides:
- `--kind concepts` - restrict to one folder
- `--min-score 0.5` - tighter (fewer candidates, less recall)
- `--min-score 0.25` - looser (more candidates, more LLM cost)
- `--top 20` - cap output to top-N highest-scoring pairs

If zero candidates: report "no redundancy detected above threshold"
and stop. Tell the user they can lower `--min-score` if they want
to widen the net.

## Step 2 - Show the user the candidate list

Surface the human summary from Step 1 (already printed by the
script) and ask before delegating: *"K candidate pairs found. Run
the `deduplicator` agent on them? It'll cost roughly K × 15 k tokens
for the judgment pass. [Y/n]"*.

## Step 3 - Delegate to the deduplicator sub-agent

Use the `Agent` tool with `subagent_type=deduplicator`. Pass the
path to `tools/.cache/redundancy_candidates.json` so the agent
doesn't re-run the pre-filter. The agent will:

1. Read each candidate's two pages.
2. Decide per pair: **Merge / Extract / Keep separate**.
3. Present a summary table.
4. Confirm each Merge / Extract with the user before applying.
5. Execute confirmed actions via `tools/merge_pages.py --apply`
   (for merges) or by writing new pages directly (for extractions).
6. Append decisions to `wiki/log.md`.

## Step 4 - Post-deduplication housekeeping

After the deduplicator completes, suggest these follow-ups:

```bash
python tools/update_cited_by.py    # refresh ## Cited By sections after slug changes
python tools/build_graph.py        # rebuild graph if many merges happened
```

And offer to run `lint` to confirm no broken wikilinks remain
(`[[deleted-slug]]` references that didn't get caught by the
rewrite).

# Cost expectation

| Step | Cost |
|---|---|
| Pre-filter (`find_redundancy.py`) | 0 tokens, ~30 s CPU |
| Deduplicator agent (K candidates) | ~K × 15 k tokens |
| Mechanical merge (`merge_pages.py --apply`) | 0 tokens |

A typical run on a 200-page wiki surfaces 10-30 candidates and costs
150-500 k tokens - comparable to ingesting one long paper.

# Hard constraints

- **NEVER skip user confirmation** for individual merge / extract
  actions, even when invoked non-interactively. Each destructive
  operation gets its own confirmation.
- **NEVER run on `wiki/sources/`** - source-level duplication is
  handled by `source-remover`, not this workflow.
- The pre-filter is a hint, not a verdict. The agent does the
  judgment; the user does the approval.
