# Recommendation Page Format

One page per topic, grouped by **strength of evidence**. Drop into
`wiki/recommendations/<topic-slug>.md`.

For guideline / meta-analysis / consensus statement papers, every
recommendation in the original recommendation table must be enumerated
(don't summarize) and routed to the appropriate per-topic recommendation
page. See `docs/rules/depth-completeness.md` (Guidelines, meta-analyses,
consensus statements).

```markdown
---
title: "Recommendations: <Topic>"
type: recommendation
domain: []                      # your domain tag(s)
tags: []
sources: []                     # auto-populated
last_updated: YYYY-MM-DD
---

## Strong Evidence (≥3 sources, replicated, including ≥1 RCT or meta-analysis)
- Recommendation 1 — sources: [[paper-a]] (p. ?), [[paper-b]] (p. ?),
  [[cervera-2020]] meta-analysis (p. ?). Evidence level: A.
- ...

## Moderate Evidence (1-2 RCTs or several non-randomized studies)
- Recommendation 2 — source: [[paper-d]] (p. ?). Not yet replicated.
  Evidence level: B.
- ...

## Conflicting Evidence
- Position A: [[paper-e]] (p. ?) recommends X.
- Position B: [[paper-f]] (p. ?) recommends not-X.
- Open question → see [[questions/<slug>]].

## Practical Notes
Actionable details (e.g. dose, duration, timing, contraindications).

## Related Recommendations
- [[recommendations/<other-topic>]]
```
