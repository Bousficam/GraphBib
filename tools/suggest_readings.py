#!/usr/bin/env python3
"""Suggest complementary readings for the wiki - internal snowball or
external forward-citation discovery.

Two modes:

INTERNAL (default) - backward snowball
    Walks `wiki/sources/`, aggregates each source's `cites:` frontmatter,
    surfaces DOIs cited by 2+ wiki sources but not yet in the wiki.

    python tools/suggest_readings.py MotorImagery
    python tools/suggest_readings.py --all
    python tools/suggest_readings.py MotorImagery --enrich   # +Crossref meta

EXTERNAL - forward citation discovery via OpenAlex
    For each wiki source with a DOI, lists the top-50 papers citing it
    (by cited_by_count). Aggregates co-citations across the wiki and
    ranks candidates by:
        score = co_citation × 100 + velocity + log10(max(1, venue_h))
    Filters: co_citation >= 2 OR (velocity >= 2.5 AND venue_h >= 30).
    Velocity = cited_by_count / max(1, age_years), normalizes the
    citation bias for recent papers.

    python tools/suggest_readings.py --forward
    python tools/suggest_readings.py --forward --since-year 2020
    python tools/suggest_readings.py --forward --top 30

OpenAlex is free, no auth needed. Cached in tools/.cache/openalex_forward.json.
"""
import argparse
import datetime as dt
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, SRC_DIR  # noqa: E402

CACHE_DIR = REPO_ROOT / "tools" / ".cache"
OPENALEX_CACHE_FILE = CACHE_DIR / "openalex_forward.json"

OPENALEX_USER_AGENT = "graphbib/0.1 (mailto:contact@example.com)"
OPENALEX_SLEEP = 0.05  # politeness, ~20 req/s
OPENALEX_PER_PAGE = 50  # cap top citers per source

DEFAULT_MIN_VELOCITY = 2.5
DEFAULT_MIN_CO_CITATION = 2
DEFAULT_MIN_VENUE_H = 30
DEFAULT_SINCE_YEAR = 2018
DEFAULT_TOP = 30


# ---------- frontmatter / source loading -----------------------------------

def parse_fm(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]
            except Exception:
                pass
    return {}, text


def load_sources():
    out = []
    if not SRC_DIR.is_dir():
        return out
    for p in sorted(SRC_DIR.rglob("*.md")):
        if p.name in {"index.md", "log.md", "overview.md"}:
            continue
        text = p.read_text(encoding="utf-8")
        fm, body = parse_fm(text)
        out.append({"path": p, "fm": fm, "body": body, "slug": p.stem})
    return out


# ---------- Crossref metadata (for --enrich on internal mode) ---------------

def crossref(doi):
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{quote(doi, safe='/:')}",
            timeout=10,
            headers={"User-Agent": OPENALEX_USER_AGENT},
        )
        r.raise_for_status()
        m = r.json()["message"]
        authors = [
            f"{a.get('given', '').strip()} {a.get('family', '').strip()}".strip()
            for a in m.get("author", [])
        ]
        year = None
        if m.get("issued", {}).get("date-parts"):
            year = m["issued"]["date-parts"][0][0]
        return {
            "title": (m.get("title") or [None])[0],
            "authors": [a for a in authors if a],
            "journal": (m.get("container-title") or [None])[0],
            "year": year,
        }
    except Exception:
        return None


# ---------- OpenAlex forward citations -------------------------------------

def load_openalex_cache():
    if OPENALEX_CACHE_FILE.exists():
        try:
            return json.loads(OPENALEX_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_openalex_cache(cache):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OPENALEX_CACHE_FILE.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def openalex_get(url, params=None):
    import requests
    r = requests.get(
        url,
        params=params,
        timeout=15,
        headers={"User-Agent": OPENALEX_USER_AGENT},
    )
    r.raise_for_status()
    time.sleep(OPENALEX_SLEEP)
    return r.json()


def fetch_forward_citers(doi, since_year, cache):
    """Return list of citer dicts: {doi, title, authors, year, venue,
    venue_h, citations}. Cached by source DOI + since_year.
    """
    cache_key = f"{doi.lower()}::since={since_year}"
    if cache_key in cache:
        return cache[cache_key]

    # Resolve OpenAlex ID via DOI
    try:
        work = openalex_get(f"https://api.openalex.org/works/doi:{doi}")
    except Exception as e:
        print(f"  ! OpenAlex error for {doi}: {type(e).__name__}", file=sys.stderr)
        cache[cache_key] = []
        return []
    work_id = work.get("id", "").rsplit("/", 1)[-1]
    if not work_id:
        cache[cache_key] = []
        return []

    # List forward citers, filter by year, sort by cited_by_count DESC
    try:
        resp = openalex_get(
            "https://api.openalex.org/works",
            params={
                "filter": f"cites:{work_id},from_publication_date:{since_year}-01-01",
                "sort": "cited_by_count:desc",
                "per-page": OPENALEX_PER_PAGE,
            },
        )
    except Exception as e:
        print(f"  ! OpenAlex error listing citers of {doi}: {type(e).__name__}", file=sys.stderr)
        cache[cache_key] = []
        return []

    out = []
    for w in resp.get("results", []):
        cdoi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
        if not cdoi:
            continue
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in (w.get("authorships") or [])
        ]
        primary = (w.get("primary_location") or {}).get("source") or {}
        out.append({
            "doi": cdoi,
            "title": w.get("title", "") or "",
            "authors": [a for a in authors if a][:5],
            "year": w.get("publication_year"),
            "venue": primary.get("display_name", "") or "",
            "venue_h": primary.get("h_index") or 0,
            "citations": w.get("cited_by_count", 0) or 0,
        })
    cache[cache_key] = out
    return out


# ---------- Filtering & scoring --------------------------------------------

def velocity(citations, year, current_year):
    age = max(1.0, current_year - (year or current_year))
    return citations / age


def passes_filter(co_cit, vel, venue_h, year, current_year,
                  min_co_cit, min_vel, min_venue_h):
    if year is None:
        return False
    if (current_year - year) < 1:
        # Too recent to judge on velocity - only co-citation matters
        return co_cit >= min_co_cit
    if co_cit >= min_co_cit:
        return True
    if vel >= min_vel and venue_h >= min_venue_h:
        return True
    return False


def composite_score(co_cit, vel, venue_h):
    return co_cit * 100 + vel + math.log10(max(1, venue_h))


# ---------- Internal mode (existing behaviour) -----------------------------

def internal_mode(args, sources):
    in_wiki = {(s["fm"].get("doi") or "").lower() for s in sources}
    in_wiki.discard("")

    if args.all:
        relevant = sources
        scope = "wiki-wide"
    else:
        token = f"[[{args.concept}]]"
        relevant = [s for s in sources if token in s["body"]]
        scope = args.concept
        if not relevant:
            sys.exit(f"No source page references [[{args.concept}]]")

    counter = Counter()
    by_doi = {}
    for s in relevant:
        for raw in s["fm"].get("cites", []) or []:
            d = str(raw).lower()
            if d in in_wiki:
                continue
            counter[d] += 1
            by_doi.setdefault(d, []).append(s["slug"])

    candidates = sorted(
        [(d, n) for d, n in counter.items() if n >= args.min],
        key=lambda t: (-t[1], t[0]),
    )

    print(f"=== {len(candidates)} candidates ({scope}, min={args.min}) ===")
    for d, n in candidates[: args.top]:
        meta = crossref(d) if args.enrich else None
        slugs = by_doi[d]
        print(f"\n  [{n}x]  {d}")
        if meta:
            authors = ", ".join((meta.get("authors") or [])[:3])
            if len(meta.get("authors") or []) > 3:
                authors += " et al."
            year = meta.get("year") or "?"
            title = meta.get("title") or "?"
            journal = meta.get("journal") or ""
            print(f"          {authors} ({year}). {title}.")
            if journal:
                print(f"          {journal}")
        cited_by = ", ".join(slugs[:5]) + ("…" if len(slugs) > 5 else "")
        print(f"          cited by: {cited_by}")


# ---------- Forward mode (new) ---------------------------------------------

def forward_mode(args, sources):
    in_wiki = {(s["fm"].get("doi") or "").lower() for s in sources}
    in_wiki.discard("")

    sources_with_doi = [
        s for s in sources if (s["fm"].get("doi") or "").strip()
    ]
    if not sources_with_doi:
        sys.exit("No source has a doi: in its frontmatter - cannot query OpenAlex.")

    cache = load_openalex_cache()
    current_year = dt.date.today().year

    print(f"  · Querying OpenAlex for {len(sources_with_doi)} sources "
          f"(since {args.since_year}, top {OPENALEX_PER_PAGE} citers each)…",
          file=sys.stderr)

    # candidate_doi → {meta, citing_wiki_slugs}
    aggregate = {}
    for i, s in enumerate(sources_with_doi, 1):
        sdoi = s["fm"]["doi"].strip()
        if i % 10 == 0:
            print(f"  · [{i}/{len(sources_with_doi)}] {sdoi}", file=sys.stderr)
        citers = fetch_forward_citers(sdoi, args.since_year, cache)
        for c in citers:
            cdoi = c["doi"].lower()
            if not cdoi or cdoi in in_wiki:
                continue
            if cdoi not in aggregate:
                aggregate[cdoi] = {"meta": c, "citing_wiki": set()}
            aggregate[cdoi]["citing_wiki"].add(s["slug"])

    save_openalex_cache(cache)

    # Score and filter
    ranked = []
    for cdoi, entry in aggregate.items():
        meta = entry["meta"]
        co_cit = len(entry["citing_wiki"])
        vel = velocity(meta["citations"], meta["year"], current_year)
        venue_h = meta["venue_h"] or 0
        if not passes_filter(co_cit, vel, venue_h, meta["year"],
                             current_year, args.min_co_citation,
                             args.min_velocity, args.min_venue_h):
            continue
        score = composite_score(co_cit, vel, venue_h)
        ranked.append({
            "doi": cdoi,
            "score": score,
            "co_cit": co_cit,
            "velocity": vel,
            "venue_h": venue_h,
            "meta": meta,
            "citing_wiki": sorted(entry["citing_wiki"]),
        })

    ranked.sort(key=lambda r: (-r["score"], -(r["meta"]["year"] or 0)))

    print(f"\n=== {len(ranked)} forward-citation candidates "
          f"(since {args.since_year}, after filter) ===\n")

    for i, r in enumerate(ranked[: args.top], 1):
        m = r["meta"]
        authors = ", ".join((m.get("authors") or [])[:3])
        if len(m.get("authors") or []) > 3:
            authors += " et al."
        title = (m.get("title") or "")[:140]
        venue = m.get("venue") or ""
        venue_h_str = f"h={r['venue_h']}" if r["venue_h"] else "h=?"
        cited_by = ", ".join(r["citing_wiki"][:5]) + (
            "…" if len(r["citing_wiki"]) > 5 else ""
        )
        print(f"#{i}  [co-cited {r['co_cit']}×]   "
              f"velocity {r['velocity']:.1f}/yr   "
              f"year {m['year']}   "
              f"citations {m['citations']}   "
              f"{venue_h_str}   "
              f"score {r['score']:.1f}")
        print(f"    {r['doi']}")
        print(f"    {authors} ({m['year']}). {title}.")
        if venue:
            print(f"    {venue}")
        print(f"    Cites yours: {cited_by}\n")


# ---------- Main -----------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("concept", nargs="?",
                    help="Concept name for internal mode (omit for --all or --forward).")
    ap.add_argument("--all", action="store_true",
                    help="Internal mode, wiki-wide (no concept filter).")
    ap.add_argument("--forward", action="store_true",
                    help="External mode - forward citations via OpenAlex.")
    ap.add_argument("--min", type=int, default=2,
                    help="Internal mode: minimum citation count (default 2).")
    ap.add_argument("--enrich", action="store_true",
                    help="Internal mode: fetch Crossref metadata for top results.")
    ap.add_argument("--top", type=int, default=DEFAULT_TOP,
                    help=f"Max candidates to print (default {DEFAULT_TOP}).")

    # Forward mode tuning
    ap.add_argument("--since-year", type=int, default=DEFAULT_SINCE_YEAR,
                    help=f"Forward: filter publication year (default {DEFAULT_SINCE_YEAR}).")
    ap.add_argument("--min-velocity", type=float, default=DEFAULT_MIN_VELOCITY,
                    help=f"Forward: minimum citations/year (default {DEFAULT_MIN_VELOCITY}).")
    ap.add_argument("--min-co-citation", type=int, default=DEFAULT_MIN_CO_CITATION,
                    help=f"Forward: minimum wiki sources cited (default {DEFAULT_MIN_CO_CITATION}).")
    ap.add_argument("--min-venue-h", type=int, default=DEFAULT_MIN_VENUE_H,
                    help=f"Forward: minimum venue h-index (default {DEFAULT_MIN_VENUE_H}).")
    args = ap.parse_args()

    sources = load_sources()
    if not sources:
        sys.exit(f"No sources under {SRC_DIR}")

    if args.forward:
        forward_mode(args, sources)
        return

    if not args.all and not args.concept:
        ap.error("Provide a concept name, or use --all (internal) or --forward (external).")

    internal_mode(args, sources)


if __name__ == "__main__":
    main()
