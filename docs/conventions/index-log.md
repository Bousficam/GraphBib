# Index and Log Formats

## `wiki/index.md`

The catalog of every wiki page. Updated on every ingest.

```markdown
# Wiki Index

## Overview
- [Overview](overview.md) — living synthesis

## Sources — Papers
- [Paper Title](sources/<slug>.md) — one-line summary (Year, Journal)

## Sources — Theses
- [Thesis Title](sources/<slug>.md) — one-line summary (Year, University)

## Concepts
- [Concept Name](concepts/<Name>.md) — one-line definition

## Methods
- [Method Name](methods/<Name>.md) — what it measures

## Interventions
- [Intervention Name](interventions/<slug>.md) — therapy family, target outcome

## Recommendations
- [Topic](recommendations/<topic>.md) — one-line scope

## Questions
- [Question](questions/<slug>.md) — status

## Entities
- [Entity Name](entities/<Name>.md) — one-line description

## Syntheses
- [Title](syntheses/<slug>.md) — what question it answers
```

## `wiki/log.md`

Append-only chronological record. Each entry starts with
`## [YYYY-MM-DD] <operation> | <title>` so it is grep-parseable:

```bash
grep "^## \[" wiki/log.md | tail -10
```

Operations: `ingest`, `query`, `review`, `cite`, `health`, `lint`,
`graph`.

## `wiki/overview.md`

Living synthesis across all sources. Refreshed when synthesis warrants
revision. The Citation Rule applies under `## Key Findings
(synthesized)`. Full template at `docs/templates/overview.md`.
