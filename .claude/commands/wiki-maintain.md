---
description: Wiki maintenance pass - runs lint then delegates fixes to librarian. Use weekly or after each batch ingestion.
argument-hint: "[--lint-only | --auto-fix-only]"
---

End-to-end maintenance: detect issues then act on them.

Arguments: $ARGUMENTS

- (no argument) - full pass: `lint` then `librarian`.
- `--lint-only` - diagnostic only, no fixes.
- `--auto-fix-only` - skip lint, run only librarian's Phase 1 (auto
  upkeep: update_cited_by, parse_references --validate,
  organize_sources --promote, coverage_report). Useful as a quick
  daily refresh.

# Procedure

## Phase 1 - Diagnose

Unless `--auto-fix-only`, delegate to lint:

```
Agent(subagent_type=lint, prompt="Full lint sweep, return the report.")
```

The sub-agent runs deterministic Tier 1 checks and cached semantic
Tier 2 checks (sha256-keyed, agent_version-aware). Returns a
severity-grouped report.

If `--lint-only`, surface the report and STOP. Tell the user how to
trigger fixes:

```
Run /wiki-maintain (without --lint-only) to delegate fixes to
librarian, or address findings manually.
```

## Phase 2 - Act

If not `--lint-only`, delegate to librarian:

```
Agent(subagent_type=librarian, prompt="Address the lint findings.")
```

The sub-agent:
- Runs Phase 1 auto-fixes (no LLM, idempotent: update_cited_by,
  parse_references --validate, organize_sources --promote,
  coverage_report).
- Phase 2 delegates: source-extender on shallow sources,
  concept-builder on stub concepts (capped at 5 per kind per session).
- Phase 3 surfaces user-confirmation items (concept duplications,
  folder moves, source removals).

If `--auto-fix-only`, skip the lint and ask librarian to run only
Phase 1.

## Phase 3 - Recap

The sub-agents return their own summaries; assemble a unified one:

```
=== /wiki-maintain - <date> ===

Lint findings: <BLOCKING>/<WARNING>/<INFO>
Auto-fixed (no LLM): <count>
Delegated to specialists: <count>
Awaiting user decision: <count>

Specialists invoked:
  - source-extender on <slug> → <result>
  - concept-builder on <concept> → <result>
  - …

Pending user input:
  - <issue> - Suggested action: <action>
  - …

Next session: <suggestions, e.g. re-run after the user-confirmed
actions are applied>
```

# Cost

- Phase 1 (lint): cache-friendly, free on unchanged files. New
  sources cost ~5-10k tokens for semantic checks.
- Phase 2 (librarian): 0 LLM for auto-fix, ~10-20k tokens per
  delegated specialist call.
- A weekly maintain on a 50-source wiki: typically <$0.50 if cache
  is warm.

# Notes

- Idempotent. Re-running this multiple times in a day is safe and
  mostly free.
- Each sub-agent has its own context window - the parent stays light.
