---
description: Generate a structured literature review on a topic from the wiki — Background / Methods / Findings / Recommendations / Open Questions / APA bibliography. Saves to wiki/syntheses/. Sonnet by default; pass --opus for higher-quality long-form synthesis on complex or high-stakes topics.
argument-hint: "<topic>  [--opus]"
---

Produce a citation-rigorous literature review on the given topic.

Arguments: $ARGUMENTS — the topic (free text) + optional `--opus`
flag at the end.

Examples:
- *"<intervention> in <population>"*
- *"<construct> as biomarker for <outcome>"*
- *"<topic> --opus"*

# Model selection

By **default the `reviewer` sub-agent runs on Sonnet** — fast, cheap,
solid quality for routine reviews.

Pass **`--opus`** at the end of the topic to upgrade for that one
run. Use it when:
- the topic spans many sources (≥ 30) and the narrative needs to
  hold together across sub-themes
- there are known contradictions in the literature you want
  carefully weighed
- the review is going into a paper / grant / guideline draft
  (user-facing output, quality matters more than cost)

Cost guide: Opus ≈ 5× Sonnet pricing. A 30-source review with
Opus ≈ $15 vs Sonnet ≈ $3. Worth it for the qualitatively better
long-form coherence on stakes-high outputs, wasteful for routine
synthesis.

# Procedure

Parse `$ARGUMENTS`:
- If `--opus` is the last token, strip it and set `MODEL=opus`.
- Otherwise, `MODEL=sonnet` (the agent's default).

Delegate to the `reviewer` sub-agent. With the model override:

```
Agent(
    subagent_type=reviewer,
    model=$MODEL,                # only set if --opus was passed
    prompt="Review topic: $TOPIC. Save to wiki/syntheses/."
)
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
- Confirm the model in your end-of-run recap: *"Review on '<topic>'
  written via <Sonnet | Opus> to wiki/syntheses/<slug>.md"* so the
  user knows what was used.
