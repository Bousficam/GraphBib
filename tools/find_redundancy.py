#!/usr/bin/env python3
"""Find redundancy candidates among wiki/concepts/, wiki/methods/, wiki/interventions/.

Deterministic pre-filter — emits a ranked list of candidate page pairs
that *might* be duplicates or overlapping topics. The LLM sub-agent
`deduplicator` then judges each candidate and proposes a merge,
extraction, or "keep separate".

The point is to avoid O(n²) LLM token cost: on a wiki with 200 concept
pages, this script reduces 19 900 possible pairs to typically 10-30
that an agent actually needs to read.

Signals (combined, no LLM):
  1. **Title / alias overlap** — same slug stems, aliased name match,
     SequenceMatcher.ratio > 0.75 between titles.
  2. **Tag Jaccard** — |tags_a ∩ tags_b| / |tags_a ∪ tags_b|.
  3. **Co-citation Jaccard** — pages that wikilink to BOTH a and b
     (the strongest signal: two concepts cited by the same papers
     are probably the same concept).
  4. **Shared outlinks Jaccard** — pages that BOTH a and b wikilink
     to (weak signal of topical proximity).
  5. **First-paragraph word-set Jaccard** — overlap of content
     vocabulary in the first ~1000 chars, after stopword removal.

A candidate pair is emitted if any of these passes a per-signal
threshold OR if the combined weighted score exceeds OVERALL_THRESHOLD.

CLI:

    python tools/find_redundancy.py                    # all kinds, default thresholds
    python tools/find_redundancy.py --kind concepts    # one folder only
    python tools/find_redundancy.py --top 20           # cap candidates
    python tools/find_redundancy.py --min-score 0.4    # tighten/loosen
    python tools/find_redundancy.py --json             # raw JSON to stdout

Output: tools/.cache/redundancy_candidates.json (always written), human
summary to stdout.

JSON schema per candidate:
  {
    "kind": "concepts" | "methods" | "interventions",
    "a": {"slug": "...", "path": "..."},
    "b": {"slug": "...", "path": "..."},
    "score": 0.78,
    "signals": {
      "title_similarity": 0.92,
      "alias_match": true,
      "tag_jaccard": 0.5,
      "cocitation_jaccard": 0.6,
      "outlink_jaccard": 0.3,
      "text_jaccard": 0.4
    },
    "rationale": ["alias match on 'event-related desynchronization'",
                  "co-cited by 4 of 7 source papers"]
  }
"""
import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, WIKI_DIR, WIKILINK_RE, parse_fm  # noqa: E402

KINDS = ("concepts", "methods", "interventions")

W_TITLE = 0.25
W_ALIAS = 0.20
W_TAG = 0.10
W_COCITE = 0.25
W_OUTLINK = 0.10
W_TEXT = 0.10

PER_SIGNAL_THRESHOLDS = {
    "title_similarity": 0.78,
    "cocitation_jaccard": 0.5,
    "tag_jaccard": 0.6,
    "text_jaccard": 0.45,
}

OVERALL_THRESHOLD = 0.35

STOPWORDS = set("""
a an the and or but if then for of in on to from with by as is are was were be been being
this that these those it its their them they we you i he she his her our your my
not no nor so do does did done has have had having can could should would may might must
will shall about into onto upon over under between among across without within
""".split())

CACHE_DIR = REPO_ROOT / "tools" / ".cache"
DEFAULT_OUTPUT = CACHE_DIR / "redundancy_candidates.json"


def _norm_tokens(text: str) -> set[str]:
    return {
        w.lower()
        for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text or "")
        if w.lower() not in STOPWORDS
    }


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _load_pages(kind: str) -> list[dict]:
    """Load every page under wiki/<kind>/ with extracted features."""
    base = WIKI_DIR / kind
    if not base.is_dir():
        return []
    pages = []
    for p in sorted(base.rglob("*.md")):
        if p.name.startswith("_") or p.name in {"index.md"}:
            continue
        text = p.read_text(encoding="utf-8")
        fm, body = parse_fm(text)
        title = (fm.get("title") or "").strip() or p.stem.replace("-", " ")
        aliases = [a.lower() for a in (fm.get("aliases") or []) if isinstance(a, str)]
        tags = {t.lower() for t in (fm.get("tags") or []) if isinstance(t, str)}
        outlinks = {m.group(1) for m in WIKILINK_RE.finditer(body)}
        head = body[:1500]
        pages.append(
            {
                "slug": p.stem,
                "path": str(p.relative_to(REPO_ROOT)),
                "title": title,
                "aliases": aliases,
                "tags": tags,
                "outlinks": outlinks,
                "tokens": _norm_tokens(head),
            }
        )
    return pages


def _build_inlink_index() -> dict[str, set[str]]:
    """For every page in the wiki, who wikilinks to it? slug → set(referrer_slugs)."""
    inlinks: dict[str, set[str]] = {}
    for p in WIKI_DIR.rglob("*.md"):
        if p.name in {"index.md", "log.md", "overview.md"}:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        referrer = p.stem
        for m in WIKILINK_RE.finditer(text):
            target = m.group(1).split("#", 1)[0].split("|", 1)[0]
            target = target.split("/")[-1]
            inlinks.setdefault(target, set()).add(referrer)
    return inlinks


def _alias_match(a: dict, b: dict) -> bool:
    pool_a = {a["title"].lower(), *a["aliases"]}
    pool_b = {b["title"].lower(), *b["aliases"]}
    return bool(pool_a & pool_b)


def _score_pair(a: dict, b: dict, inlinks: dict) -> tuple[float, dict, list[str]]:
    title_sim = SequenceMatcher(None, a["title"].lower(), b["title"].lower()).ratio()
    alias_hit = _alias_match(a, b)
    tag_j = _jaccard(a["tags"], b["tags"])
    refs_a = inlinks.get(a["slug"], set())
    refs_b = inlinks.get(b["slug"], set())
    cocite_j = _jaccard(refs_a, refs_b)
    outlink_j = _jaccard(a["outlinks"], b["outlinks"])
    text_j = _jaccard(a["tokens"], b["tokens"])

    score = (
        W_TITLE * title_sim
        + W_ALIAS * (1.0 if alias_hit else 0.0)
        + W_TAG * tag_j
        + W_COCITE * cocite_j
        + W_OUTLINK * outlink_j
        + W_TEXT * text_j
    )

    signals = {
        "title_similarity": round(title_sim, 3),
        "alias_match": alias_hit,
        "tag_jaccard": round(tag_j, 3),
        "cocitation_jaccard": round(cocite_j, 3),
        "outlink_jaccard": round(outlink_j, 3),
        "text_jaccard": round(text_j, 3),
    }

    rationale = []
    if alias_hit:
        rationale.append("alias / title overlap")
    if title_sim >= PER_SIGNAL_THRESHOLDS["title_similarity"]:
        rationale.append(f"title similarity {title_sim:.2f}")
    if cocite_j >= PER_SIGNAL_THRESHOLDS["cocitation_jaccard"]:
        rationale.append(
            f"co-cited by {len(refs_a & refs_b)} of {len(refs_a | refs_b)} referrers"
        )
    if tag_j >= PER_SIGNAL_THRESHOLDS["tag_jaccard"]:
        rationale.append(f"tag overlap {tag_j:.2f}")
    if text_j >= PER_SIGNAL_THRESHOLDS["text_jaccard"]:
        rationale.append(f"first-paragraph vocab overlap {text_j:.2f}")

    return score, signals, rationale


def _keep(score: float, signals: dict) -> bool:
    if score >= OVERALL_THRESHOLD:
        return True
    for sig, threshold in PER_SIGNAL_THRESHOLDS.items():
        if isinstance(signals[sig], bool):
            if signals[sig]:
                return True
        elif signals[sig] >= threshold:
            return True
    return False


def find_redundancy(kinds: list[str], top: int | None) -> list[dict]:
    inlinks = _build_inlink_index()
    candidates: list[dict] = []
    for kind in kinds:
        pages = _load_pages(kind)
        for i, a in enumerate(pages):
            for b in pages[i + 1 :]:
                score, signals, rationale = _score_pair(a, b, inlinks)
                if not _keep(score, signals):
                    continue
                candidates.append(
                    {
                        "kind": kind,
                        "a": {"slug": a["slug"], "path": a["path"], "title": a["title"]},
                        "b": {"slug": b["slug"], "path": b["path"], "title": b["title"]},
                        "score": round(score, 3),
                        "signals": signals,
                        "rationale": rationale,
                    }
                )
    candidates.sort(key=lambda c: c["score"], reverse=True)
    if top:
        candidates = candidates[:top]
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--kind", choices=KINDS, action="append")
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--min-score", type=float, default=None)
    parser.add_argument("--json", action="store_true", help="JSON to stdout, no human summary")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    if args.min_score is not None:
        global OVERALL_THRESHOLD
        OVERALL_THRESHOLD = args.min_score

    kinds = args.kind or list(KINDS)
    candidates = find_redundancy(kinds, args.top)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.output)
    out.write_text(json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(candidates, indent=2, ensure_ascii=False))
        return

    if not candidates:
        print(f"No redundancy candidates above threshold (min-score={OVERALL_THRESHOLD}).")
        print(f"Cache: {out}")
        return

    print(f"{len(candidates)} candidate(s) — sorted by score, top to read first:\n")
    for i, c in enumerate(candidates, 1):
        print(f"{i:>2}. [{c['kind']}]  {c['a']['slug']}  ↔  {c['b']['slug']}   (score {c['score']})")
        for r in c["rationale"]:
            print(f"      • {r}")
        print()
    print(f"Full JSON: {out}")
    print("\nNext step: invoke the `deduplicator` sub-agent to judge each candidate.")


if __name__ == "__main__":
    main()
