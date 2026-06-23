# Question Page Format

Captures gaps and open research questions identified across the
literature. One page per question, in `wiki/questions/<slug>.md`.

```markdown
---
title: "Open Question: <one-line question>"
type: question
status: "open"                  # open | partially-answered | resolved
raised_by: [[source-slug]]      # source(s) that explicitly raise it
domain: []                      # your domain tag(s)
tags: []
last_updated: YYYY-MM-DD
---

## The Gap
1-3 sentences stating what is unknown.

## Why It Matters
Clinical, theoretical, or methodological stakes.

## What's Known
- [[paper-a]] (p. ?) shows ...
- [[paper-b]] (p. ?) suggests ...

## What's Missing
- Specific evidence type missing (e.g., long-term follow-up RCT).
- Specific population missing (e.g., an under-studied sub-group).

## Suggested Studies
- Design 1 that would close the gap.
- Design 2.

## Connections
- Concerns [[ConceptName]].
- Would test [[FrameworkName]].
- Methodology candidate: [[methods/...]].
```
