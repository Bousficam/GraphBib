---
description: Batch-ingest a directory of source markdown files via the ingester sub-agent, with confirmation between batches.
argument-hint: "<DIR> [batch-size]"
---

Batch-ingest the markdown files under the given directory by delegating
each one to the `ingester` sub-agent. This is the entry point for
processing a freshly-converted PDF library (output of `/wiki-convert`).

Arguments: $ARGUMENTS

- The first argument is `DIR` — the directory containing the source `.md`
  files to ingest (e.g. `raw/<vault>/papers/`, `raw/<vault>/papers/articles/bci/`,
  or `raw/<vault>/theses/<slug>/`).
- The second argument, if provided, is `BATCH_SIZE` — number of papers
  to ingest before confirming with the user (default: 5).

# Procedure

1. **Discover**: list `*.md` files under `DIR` (recursive). Skip files
   whose corresponding `wiki/sources/.../<slug>.md` already exists
   (idempotent; user can re-trigger via `source-extender` for those).
   Sort by file size ascending — shortest papers first to fail fast.

2. **Confirm scope**: report
   `"Found N markdown files to ingest under <DIR>. M already in the
   wiki, P new to ingest. Batch size B. Proceed? [Y/n]"` — wait for
   user confirmation before starting.

3. **For each batch of B files**:
   a. For each file in the batch, invoke the **`ingester`** sub-agent
      with the file path. Use the `Agent` tool with
      `subagent_type=ingester` and prompt: `"Ingest <path>"`.
   b. Collect each sub-agent's summary line (`INGEST COMPLETE` /
      `INGEST INCOMPLETE: <reason>`).
   c. After the batch, surface a short status block:
      ```
      Batch <i>/<total>: completed <ok>/<batch>, incomplete <ko>
      Issues:
        - <slug>: <reason>
      Continue? [Y/n]
      ```
      Wait for user confirmation before the next batch (unless `n`,
      stop).

4. **After all batches**: surface a final summary:
   ```
   Total ingested: <N>
   Entities created: <count>
   Concepts touched: <count>
   Methods touched: <count>
   Recommendations created: <count>
   Questions surfaced: <count>
   Snowball candidates surfaced: <count>
   ```

5. **Suggest follow-ups**:
   - Run `python tools/update_cited_by.py` to refresh the citation
     network.
   - Run `python tools/consolidate_concepts.py --since 1d` to extend
     concept pages from the new ingests.
   - Run `python tools/coverage_report.py` to see depth status.

# Defaults

- Batch size: 5 (good trade-off between feedback and throughput).
- Sort: shortest-first (fail fast on bad PDFs).
- Skip already-ingested: yes (idempotent).
- Concurrency: serial (one ingester at a time — sub-agents run sequentially).

# Failure handling

- An incomplete sub-agent run (returning `INGEST INCOMPLETE`) does NOT
  stop the batch; the failure is logged and the next file proceeds.
- Network errors or sub-agent timeouts: log the slug to a "deferred"
  list and surface it in the final summary.
- The user can re-run `/wiki-batch-ingest` later — already-ingested
  files are skipped, so only the deferred and newly added files get
  processed.

# Notes

- Each ingester invocation has its own context window, so a long
  CLAUDE.md / templates load is amortized over the sub-agent's
  workload, not the parent's.
- The parent agent (you) stays orchestrator: don't ingest yourself —
  delegate.
- For theses (`raw/<vault>/theses/<slug>/`), the parent ingestion order
  matters: ingest the parent thesis MD FIRST, then chapters in
  numerical order. Apply the rule from
  `docs/workflows/long-document-ingestion.md`.
