---
description: Answer a focused research question by synthesizing the wiki — citation-grounded, APA bibliography, optional save as a synthesis page.
argument-hint: "<question>"
---

Answer a research question with synthesis across the wiki, every
factual claim cited.

Arguments: $ARGUMENTS — the full question, e.g.
*"what does the literature say about the dose-response of <intervention>
in <population>?"*

# Procedure

## Step 1 — Delegate to query-synthesizer

```
Agent(subagent_type=query-synthesizer, prompt="$ARGUMENTS")
```

The sub-agent:
- Decomposes the question (concept / intervention / population /
  outcome).
- Reads `wiki/index.md` and the relevant pages (sources, concepts,
  methods, recommendations, questions).
- Produces a 3–8 paragraph answer organized by sub-claim, every
  claim citing `[[source]] (p. ?)`.
- Applies the Indirect Citation Rule: claims attributed to prior
  work via a wiki paper's discussion cite the originating paper Y,
  not the transmitter X.
- Closes with an APA bibliography auto-generated from each cited
  source's `citation_apa` frontmatter.
- Surfaces gaps (questions the corpus can't yet answer, snowball
  candidates).

## Step 2 — Optional save

After the synthesizer returns its answer, ask:

```
Save this as wiki/syntheses/<topic-slug>.md? [Y/n]
```

If yes, the sub-agent will already have proposed a slug — write the
file. Otherwise just print the synthesis to the chat.

# Notes

- For a broader topic that warrants a structured literature review
  (Background / Methods / Findings / Recommendations / Open Questions
  / Bibliography), use `/wiki-review` instead.
- For a quick "give me 3 APA refs on X" without synthesis, ask the
  agent in plain English (no specific slash command — the wiki is
  navigable enough).
- This command always saves with a fresh `last_updated` timestamp;
  re-running on the same topic overwrites the synthesis page.
