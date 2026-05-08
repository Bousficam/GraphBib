---
description: Generate a structured literature review on a topic from the wiki — Background / Methods / Findings / Recommendations / Open Questions / APA bibliography. Saves to wiki/syntheses/.
argument-hint: "<topic>"
---

Produce a citation-rigorous literature review on the given topic.

Arguments: $ARGUMENTS — the topic (free text), e.g.
*"MI-BCI in chronic stroke"*, *"corticospinal integrity as biomarker
for motor recovery"*, *"cTBS over contralesional M1"*.

# Procedure

Delegate to the `reviewer` sub-agent:

```
Agent(subagent_type=reviewer, prompt="Review topic: $ARGUMENTS. Save to wiki/syntheses/.")
```

The sub-agent:
- Reads `wiki/index.md` and gathers all sources tagged with the topic
  (search by `domain`, `tags`, `intervention_family`, or
  `[[wikilinks]]`).
- Reads relevant `wiki/concepts/`, `wiki/methods/`,
  `wiki/recommendations/`, `wiki/questions/` pages.
- Writes a structured Markdown review to
  `wiki/syntheses/<topic-slug>-review.md` with sections:
  - Background and Key Concepts
  - Methods Used in the Literature (table)
  - Main Findings (sub-themes)
  - Recommendations
  - Open Questions
  - Bibliography (APA, auto-generated from `citation_apa`)
- Applies the Indirect Citation Rule: claims attributed to prior
  work via a wiki paper's discussion cite the originating paper Y.
- Numerical results quoted verbatim.

# Notes

- For a focused question rather than a structured review, use
  `/wiki-query` instead.
- If fewer than 5 sources cover the topic, the sub-agent will warn
  and suggest running `/wiki-discover <topic>` first to ingest more
  sources.
- The review file is overwritten on re-runs (the synthesis is
  regenerated from the current wiki state). Manual edits to the
  saved file should be made after the agent finishes, not before.
- Word count target: 1500–4000 words depending on topic breadth.
