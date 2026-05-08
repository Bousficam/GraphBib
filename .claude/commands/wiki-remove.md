---
description: Cleanly remove a source from the wiki + every cross-reference (mistaken ingest, retraction, off-topic). Always dry-run first.
argument-hint: "<source-slug>"
---

Remove a source and clean up all references to it across the wiki.

Arguments: $ARGUMENTS — the source slug to remove (e.g.
`cervera-2020`).

# Procedure

Delegate to the `source-remover` sub-agent:

```
Agent(subagent_type=source-remover, prompt="Remove $ARGUMENTS")
```

The sub-agent:

1. Always runs `python tools/remove_source.py <slug>` first (dry-run).
2. Surfaces every change that would be made — wikilinks dropped /
   rewritten across concept / method / intervention / recommendation /
   question pages, DOI removed from other sources' `cites:` arrays,
   `## Cited By` entries cleaned, `wiki/index.md` and `wiki/log.md`
   mentions.
3. Highlights risky changes (claims that would become orphaned —
   only this source supported them).
4. **Waits for explicit user confirmation** before applying.
5. Suggests `git add -A && git commit -m "snapshot before remove"`
   as a safety net.
6. On approval, runs `--apply`, then `python tools/update_cited_by.py`
   to refresh derived sections.
7. Commits with `remove source: <slug> (<reason>)`.

# Notes

- This is destructive but git-tracked — `git revert HEAD` undoes it.
- Use `--strict` (sub-agent will ask) to also drop bullets where the
  slug was the SOLE supporting source. Without `--strict`, orphan
  claims survive — review concept pages manually after.
- For multi-source removal, run this command once per slug. The
  sub-agent refuses bulk removal to keep dry-runs interpretable.
- The sub-agent refuses to remove a thesis with already-ingested
  chapters, or a source cited by an active synthesis page, without
  explicit override.
