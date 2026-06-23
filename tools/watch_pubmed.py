#!/usr/bin/env python3
"""Watch PubMed and bioRxiv for new publications matching saved queries.

Reads a config file (`tools/watch_queries.yaml`) listing PubMed search
strings to monitor. For each query, queries the NCBI E-utilities API,
filters out PMIDs already seen (cached in `tools/.cache/pubmed_seen.json`),
and writes a Markdown report of new candidates with title, authors,
journal, year, DOI, and abstract.

The bioRxiv layer is optional (--biorxiv) and queries the bioRxiv API.

Usage:
    python tools/watch_pubmed.py
    python tools/watch_pubmed.py --since 2025-10-01
    python tools/watch_pubmed.py --biorxiv
    python tools/watch_pubmed.py --save
    python tools/watch_pubmed.py --init    # writes a starter watch_queries.yaml

Config (tools/watch_queries.yaml):

    queries:
      - name: "MI-BCI stroke"
        pubmed: "(motor imagery[Title/Abstract]) AND (BCI OR brain-computer interface) AND stroke"
      - name: "TMS stroke motor recovery"
        pubmed: "TMS[Title/Abstract] AND stroke[Title/Abstract] AND motor recovery"
      - name: "DTI corticospinal tract stroke"
        pubmed: "DTI[Title/Abstract] AND corticospinal AND stroke"
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

REPO_ROOT = Path(__file__).parent.parent
CACHE_DIR = REPO_ROOT / "tools" / ".cache"
CACHE_FILE = CACHE_DIR / "pubmed_seen.json"
CONFIG_FILE = REPO_ROOT / "tools" / "watch_queries.yaml"

ENTREZ = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BIORXIV = "https://api.biorxiv.org/details/biorxiv"

USER_AGENT = "graphbib-watcher/0.1 (mailto:contact@example.com)"

STARTER_CONFIG = """\
# Saved queries for tools/watch_pubmed.py.
# Each query targets PubMed via the E-utilities API.
#
# Replace the placeholders below with queries for YOUR research domain.
# PubMed query syntax: https://pubmed.ncbi.nlm.nih.gov/help/

queries:
  - name: "example query 1"
    pubmed: "(your topic[Title/Abstract]) AND (another term)"

  - name: "example query 2"
    pubmed: "your intervention[Title/Abstract] AND your outcome"
"""


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def pubmed_search(query, since_date=None, retmax=50):
    """Return list of PMIDs matching the query."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "json",
        "sort": "date",
    }
    if since_date:
        params["mindate"] = since_date.replace("-", "/")
        params["datetype"] = "pdat"
    r = requests.get(
        f"{ENTREZ}/esearch.fcgi",
        params=params,
        timeout=15,
        headers={"User-Agent": USER_AGENT},
    )
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def pubmed_summary(pmids):
    """Return list of dicts with title, authors, journal, year, DOI for given PMIDs."""
    if not pmids:
        return []
    r = requests.get(
        f"{ENTREZ}/esummary.fcgi",
        params={"db": "pubmed", "id": ",".join(pmids), "retmode": "json"},
        timeout=20,
        headers={"User-Agent": USER_AGENT},
    )
    r.raise_for_status()
    items = r.json().get("result", {})
    out = []
    for pmid in pmids:
        meta = items.get(pmid)
        if not meta:
            continue
        title = meta.get("title", "").rstrip(".")
        authors = [a.get("name", "") for a in meta.get("authors", [])][:5]
        journal = meta.get("fulljournalname") or meta.get("source", "")
        pubdate = meta.get("pubdate", "")
        year_m = re.search(r"\d{4}", pubdate)
        year = year_m.group(0) if year_m else None
        doi = ""
        for aid in meta.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")
                break
        out.append({
            "pmid": pmid,
            "title": title,
            "authors": authors,
            "journal": journal,
            "year": year,
            "doi": doi,
        })
    return out


def biorxiv_search(query, since_date=None, retmax=20):
    """Lightweight bioRxiv keyword filter on recent publications.

    bioRxiv API doesn't expose full-text search; we fetch recent papers
    and grep titles/abstracts client-side. since_date format YYYY-MM-DD.
    """
    if not since_date:
        since_date = datetime.now().strftime("%Y-%m-01")
    today = datetime.now().strftime("%Y-%m-%d")
    keywords = [w.lower() for w in re.findall(r"\w{4,}", query)]
    out = []
    cursor = 0
    while len(out) < retmax and cursor < 200:
        url = f"{BIORXIV}/{since_date}/{today}/{cursor}"
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            items = r.json().get("collection", [])
        except Exception:
            break
        if not items:
            break
        for it in items:
            blob = (it.get("title", "") + " " + it.get("abstract", "")).lower()
            if all(k in blob for k in keywords):
                out.append({
                    "pmid": "",
                    "title": it.get("title", ""),
                    "authors": [it.get("authors", "")][:5],
                    "journal": "bioRxiv (preprint)",
                    "year": (it.get("date", "") or "")[:4],
                    "doi": it.get("doi", ""),
                    "source": "biorxiv",
                })
        cursor += len(items)
        time.sleep(0.2)
    return out[:retmax]


def render(report):
    lines = ["# PubMed / bioRxiv watch", ""]
    if not report:
        lines.append("*(No new candidates across saved queries.)*")
        return "\n".join(lines)
    for query_name, items in report.items():
        lines.append(f"## {query_name} ({len(items)} new)")
        lines.append("")
        for it in items:
            authors = ", ".join((it.get("authors") or [])[:3])
            if len(it.get("authors") or []) > 3:
                authors += " et al."
            year = it.get("year") or "?"
            title = it.get("title") or "?"
            journal = it.get("journal") or ""
            doi = it.get("doi") or ""
            lines.append(f"- **{title}**")
            lines.append(f"  {authors} · {journal} ({year})")
            if doi:
                lines.append(f"  DOI: `{doi}` — https://doi.org/{doi}")
            if it.get("pmid"):
                lines.append(f"  PMID: {it['pmid']} — https://pubmed.ncbi.nlm.nih.gov/{it['pmid']}/")
            lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="Earliest publication date (YYYY-MM-DD)")
    ap.add_argument("--biorxiv", action="store_true", help="Also query bioRxiv")
    ap.add_argument("--save", action="store_true", help="Write report to wiki/watch-report.md")
    ap.add_argument("--init", action="store_true", help="Write a starter watch_queries.yaml")
    args = ap.parse_args()

    if args.init:
        if CONFIG_FILE.exists():
            sys.exit(f"{CONFIG_FILE} already exists.")
        CONFIG_FILE.write_text(STARTER_CONFIG, encoding="utf-8")
        print(f"  ✓ {CONFIG_FILE.relative_to(REPO_ROOT)} created — edit and re-run.", file=sys.stderr)
        return

    if not CONFIG_FILE.exists():
        sys.exit(f"No config at {CONFIG_FILE}. Run `--init` to scaffold one.")

    cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    queries = cfg.get("queries") or []
    if not queries:
        sys.exit("No queries in config")

    cache = load_cache()
    cache.setdefault("seen_pmids", [])
    cache.setdefault("seen_dois", [])
    seen_pmids = set(cache["seen_pmids"])
    seen_dois = set(cache["seen_dois"])

    report = {}
    for q in queries:
        name = q.get("name") or q.get("pubmed")
        print(f"[{name}] querying PubMed…", file=sys.stderr)
        try:
            pmids = pubmed_search(q["pubmed"], since_date=args.since)
        except Exception as e:
            print(f"  ! PubMed error: {e}", file=sys.stderr)
            pmids = []
        new_pmids = [p for p in pmids if p not in seen_pmids]
        items = pubmed_summary(new_pmids) if new_pmids else []

        if args.biorxiv:
            print(f"[{name}] querying bioRxiv…", file=sys.stderr)
            try:
                biox = biorxiv_search(q["pubmed"], since_date=args.since)
                items += [b for b in biox if b["doi"] not in seen_dois]
            except Exception as e:
                print(f"  ! bioRxiv error: {e}", file=sys.stderr)

        if items:
            report[name] = items
            for it in items:
                if it.get("pmid"):
                    seen_pmids.add(it["pmid"])
                if it.get("doi"):
                    seen_dois.add(it["doi"])

    cache["seen_pmids"] = sorted(seen_pmids)
    cache["seen_dois"] = sorted(seen_dois)
    save_cache(cache)

    output = render(report)
    if args.save:
        target = REPO_ROOT / "wiki" / "watch-report.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output + "\n", encoding="utf-8")
        print(f"  ✓ {target.relative_to(REPO_ROOT)}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
