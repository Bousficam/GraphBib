---
description: Quick dashboard of the wiki - counts, recent activity, coverage thinness, pending PRs, snowball debt. Zero LLM calls.
argument-hint: ""
---

One-shot status snapshot of the wiki. No actions, no LLM, just numbers.

# Procedure

Run these in parallel and assemble the report:

```bash
# Page counts
echo "=== Counts ==="
find wiki/sources -name "*.md" | wc -l        # source pages
find wiki/concepts -name "*.md" | wc -l        # concept pages
find wiki/methods -name "*.md" | wc -l         # method pages
find wiki/interventions -name "*.md" | wc -l   # intervention pages
find wiki/recommendations -name "*.md" | wc -l # recommendation pages
find wiki/questions -name "*.md" | wc -l       # question pages
find wiki/entities -name "*.md" | wc -l        # entity pages
find wiki/syntheses -name "*.md" | wc -l       # synthesis pages

# Recent activity
echo "=== Last 10 ingest log entries ==="
grep "^## \[" wiki/log.md | head -10

# Coverage thinness
echo "=== Coverage ==="
python tools/coverage_report.py 2>/dev/null | head -30

# Snowball debt (DOIs cited 2+ times but not in wiki)
echo "=== Snowball candidates (top 10) ==="
python tools/suggest_readings.py --all --min 2 2>/dev/null | head -25

# Pending git work
echo "=== Git state ==="
git log --oneline origin/main..HEAD 2>/dev/null | head
git status --short

# Lint cache health
echo "=== Lint cache ==="
python tools/lint_cache.py cache --status 2>/dev/null
```

# Output structure

```markdown
=== Wiki status - <date> ===

## Counts
| Type | Count |
|---|---|
| Sources | <N> |
| Concepts | <N> |
| Methods | <N> |
| Interventions | <N> |
| Recommendations | <N> |
| Questions | <N> |
| Entities | <N> |
| Syntheses | <N> |

## Recent activity (last 10 ingests)
- [<date>] ingest | <Title 1>
- [<date>] ingest | <Title 2>
- …

## Coverage thinness (top 5 priorities)
- [[ConceptName]] - N sources, M words (stub)
- …

## Snowball candidates (top 10 by frequency)
- [Nx] <DOI> - cited by [a, b, c, …]
- …

## Git
- Local main ahead of origin/main: <K> commits
- Untracked: <files>
- Modified: <files>
- Pending PR branches: <list>

## Lint cache
- Agent version: <v>
- Cached entries: <N>
- Last run: <date>
```

# Notes

- All operations are read-only. No changes to wiki/, no LLM calls.
- Run before starting a session to know where to focus.
- Run after `/wiki-batch-ingest` to confirm growth.
- For deeper diagnostic, use `/wiki-maintain --lint-only`.
- For action, use `/wiki-discover` (input side) or `/wiki-maintain`
  (quality side).
