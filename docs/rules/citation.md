# Citation Rule (full spec)

CLAUDE.md carries the short summary; this file is the authoritative
reference for the agent during ingest and review.

## Global rule

**Every factual claim, finding, recommendation, or quantitative
statement in any wiki page MUST cite at least one
`[[source-slug]] (p. N)`.**

- If the page number is unknown, write `(p. ?)` - do not omit the
  citation.
- Never paraphrase numerical results, p-values, or effect sizes - quote
  them verbatim with page reference.
- If a claim is the agent's synthesis across multiple sources, list all
  of them: `(see [[paper-a]] p. 12, [[paper-b]] p. 4)`.
- **Entity pages**: every biographical, affiliative, or institutional
  statement cites a source with page number, exactly like factual
  claims in source pages.
- **Overview**: every cross-source claim under
  `## Key Findings (synthesized)` cites the relevant sources. Pure
  scope/meta sentences need no citation.
- **Bibliographic fields rule**: `title`, `authors`, `journal`, `year`,
  `doi`, `source_pdf` MUST be copied verbatim from the source
  frontmatter. Never infer, translate, normalize, or invent values.
  Leave fields empty if missing in the source.
- **Default citation style**: APA 7th edition. Generated `citation_apa`
  and `bibtex_key` fields are stored in each source page's frontmatter
  and rendered in the `## How to Cite` section.

## Indirect Citation Rule (literature vs results)

A paper has two epistemic registers - claims it *inherits* from prior
work (intro / discussion / theoretical framework) and claims it
*originates* itself (methods / results). The agent must respect that
distinction.

- A claim found in the **Introduction** or **Discussion** of paper X is
  X attributing the claim to another paper Y. Cite the original:
  - **If Y is in the wiki**: cite `[[paper-Y]] (p. ?)` directly. X is
    the path through which you found Y, but Y is the citable source.
  - **If Y is not in the wiki**: cite `[[paper-X]] (p. ?, citing Y, YYYY)`
 - explicit acknowledgement that you read X but the claim originates
    in Y. Add Y to the snowball candidate list (X's `cites:`
    frontmatter).
- A claim from the **Results** of X is X's own contribution: cite
  `[[paper-X]] (p. ?)` directly.
- A claim from the **Methods** of X (procedure used by X) is also X's:
  cite `[[paper-X]] (p. ?)`.
- Numerical results (effect sizes, p-values, sample N) MUST be quoted
  verbatim from the originating paper's Results section, never via a
  secondary citation.

## Provenance pattern: `reported via [[X]]`

To make the citation chain auditable, every reported (indirect) citation
must carry the path you took to find it. Three forms only:

| Situation | Form |
|---|---|
| You read Y directly | `[[Y]] (p. 8)` |
| You read X, X cites Y, Y is in the wiki | `[[Y]] (p. 8, reported via [[X]] intro p. 4)` |
| You read X, X cites Y, Y is NOT in the wiki | `[[X]] (p. 4, citing Y 2018)` + add Y's DOI to `cites:` |

The `reported via [[X]]` annotation is **mandatory**, not optional. It
lets a future reader (or you, six months later) reconstruct *how* the
claim entered the wiki. If Y is later ingested and supersedes X's
interpretation, you can find every claim that depended on the X-routed
version.

## Knowledge construction from introductions

A paper's Introduction and Discussion are essentially mini-reviews of
prior work. They are the most efficient route to enrich concept pages
with **inherited** claims. Treat them as primary material:

1. **Extract every cited claim from `Introduction`/`Discussion` into the
   source page's `## Background (from cited literature)`**, one bullet
   per claim, each citing the original Y per the Indirect Citation Rule.
   For an empirical paper expect 5-15 bullets; for a thesis introduction
   or a review, 20+.
2. **When extending a concept page from a paper's intro**, the new
   bullet under `## Empirical Evidence` or `## Theoretical Foundations`
   MUST cite the originating paper Y (with `reported via [[X]]`),
   **never** the transmitter X alone. Otherwise the concept page
   becomes a network of who-said-what-when rather than a knowledge map.
3. **Do not rewrite Y's claim from your own knowledge** - quote or
   paraphrase what X says about Y, with X's framing made explicit. If
   X distorts Y, that distortion belongs in the wiki entry (with a
   contradiction flag if Y is also in the wiki).
