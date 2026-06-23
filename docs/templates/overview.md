# Overview Page Format

`wiki/overview.md` is a living synthesis across all sources. Refreshed
at the appropriate ingest step when synthesis warrants revision. The
Citation Rule applies under `## Key Findings (synthesized)` — pure
scope/meta sentences need no citation.

```markdown
---
title: "Wiki Overview"
type: synthesis
last_updated: YYYY-MM-DD
sources: []                 # auto-populated: all sources synthesized here
---

## Scope
1-3 sentences: what this wiki covers (no citation needed — meta).

## Key Findings (synthesized)
Cross-source claims, **each with citations**:
- Finding 1 (see [[paper-a]] p. ?, [[paper-b]] p. ?, [[cervera-2020]]
  meta-analysis p. ?)
- Finding 2 (see [[thesis-x]] ch. 4 p. ?, [[paper-c]] p. ?)

## Major Concepts
Linked, not redefined here:
- [[ConceptA]], [[ConceptB]], [[ConceptC]]

## Major Methods
- [[methods/MethodA]], [[methods/MethodB]], [[methods/MethodC]]

## Active Debates
Linked to question pages:
- Debate 1 → [[questions/<slug>]]
- Debate 2 → [[questions/<slug>]]

## Recent Updates
Append-only mini-log of synthesis-affecting ingests:
- YYYY-MM-DD : ingested [[new-paper]] — refined Finding X
- YYYY-MM-DD : ingested [[new-thesis]] — added Debate 2
```
