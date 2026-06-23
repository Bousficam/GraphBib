# Method Page Format

A method page documents a **measurement instrument**, scale, technique,
or analysis pipeline. Distinct from intervention pages (treatments
delivered to patients). One page per method, in
`wiki/methods/<MethodName>.md`.

```markdown
---
title: "EEG (Electroencephalography)"
type: method
aka: ["electroencephalography"]
category: "neurophysiology"     # imaging | neurophysiology | behavioral |
                                # subjective-scale | stimulation | analysis
measures: ["cortical activity", "alertness", "ERD/ERS"]
strengths: ["high temporal resolution", "non-invasive", "low cost"]
limitations: ["low spatial resolution", "muscle/eye artifacts"]
domain: [neurophysiology, BCI]
tags: []
sources: []                     # auto-populated
last_updated: YYYY-MM-DD
---

## Definition
1-2 sentences with citation:
*"EEG records ..."* ([[paper-x]] p. ?).

## When to Use It
- Use case 1 - established in [[paper-a]] (p. ?), [[paper-b]] (p. ?).
- Use case 2 - emerging, see [[paper-c]] (p. ?).

## Best Practices
Synthesized recommendations across the wiki's sources:
- Practice 1 - consensus across [[paper-a]], [[paper-b]] (p. ? each).
- Practice 2 - [[paper-c]] recommends ... (p. ?), but [[paper-d]]
  disagrees (p. ?).

## Common Pitfalls
- Pitfall 1 - flagged by [[paper-x]] (p. ?).

## Variants / Sub-Methods
- Variant A → [[methods/EEG-ERD]]
- Variant B → [[methods/EEG-SSVEP]]

## Used In This Wiki
*(Auto-populated: [[source-slug]] entries that report using this method.
Each entry MUST include a 1-2 sentence description of how that source
used the method - parameters, sample, deviations from standard
protocol - not just a bare wikilink.)*
```
