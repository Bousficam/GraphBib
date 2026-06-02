#!/usr/bin/env python3
"""Deduplicate a merged article list for PRISMA screening.

Reads every `*.csv` in `<project>/screening/identified/`, normalizes
column names, merges by best-available identifier, and writes
`<project>/screening/dedup.csv` plus a human-readable
`<project>/screening/reports/dedup-log.md`.

Identifier priority for dedup (highest wins):
    1. DOI (normalized: lowercase, strip URL prefix)
    2. PMID (digit-only string)
    3. Fuzzy key: normalized_title + first_author_lastname + year
       (SequenceMatcher ratio >= 0.92 over the title token)

Lenient column mapping (case-insensitive, aliases supported):
    title       <-  Title, article_title, ti
    authors     <-  Authors, author, au
    year        <-  Year, publication_year, py, pub_year
    doi         <-  DOI, digital_object_identifier
    pmid        <-  PMID, pubmed_id
    abstract    <-  Abstract, ab
    journal     <-  Journal, source, jt, journal_title
    source_db   <-  Database, source_database, db
                    (auto-filled from the CSV filename if missing)

Any extra columns are preserved verbatim under their original names.

Usage:
    python tools/screen_dedupe.py project-review/<name>
    python tools/screen_dedupe.py project-review/<name> --strict
        # --strict: do NOT use fuzzy title matching, only DOI + PMID

Idempotent: re-runs overwrite dedup.csv with the same result for the
same inputs (input order does not change which record wins).
"""
import argparse
import csv
import re
import sys
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

COL_ALIASES = {
    "title": {"title", "article_title", "articletitle", "ti", "primary_title"},
    "authors": {"authors", "author", "au", "author_names", "authornames"},
    "year": {"year", "publication_year", "publicationyear", "py", "pub_year", "pubyear"},
    "doi": {"doi", "digital_object_identifier"},
    "pmid": {"pmid", "pubmed_id", "pubmedid"},
    "abstract": {"abstract", "ab"},
    "journal": {"journal", "source", "jt", "journal_title", "journaltitle", "venue"},
    "source_db": {"source_db", "database", "source_database", "db", "src_db"},
}

CANONICAL_COLS = [
    "slug", "doi", "pmid", "title", "authors", "first_author",
    "year", "journal", "abstract", "source_dbs", "merged_count", "merged_from",
    # DOI hygiene columns — populated by screen_fetch_metadata.py
    # (see /extractor-screen-validate). Always emitted so the schema is
    # stable across runs; left empty when the validation pass hasn't
    # run yet.
    "doi_status",        # valid | recovered | invalid | unverifiable | missing
    "doi_title_match",   # true | false | "" (when no DOI or no title)
    "doi_year_match",    # true | false | ""
    "slug_rehabilitated",  # true | "" (anon-YYYY → <family>-YYYY)
]


# ----------------------------------------------------------------------
# Normalizers

DOI_URL_RE = re.compile(r"^https?://(dx\.)?doi\.org/", re.I)


def norm_doi(raw):
    if not raw:
        return ""
    s = str(raw).strip()
    s = DOI_URL_RE.sub("", s)
    s = s.strip(" .;,")
    return s.lower() if s.startswith("10.") else ""


def norm_pmid(raw):
    if not raw:
        return ""
    s = str(raw).strip()
    digits = "".join(c for c in s if c.isdigit())
    return digits if digits else ""


def norm_text(s):
    """Lowercase, strip accents, collapse non-alnum to single space."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


_TRAILING_INITIALS_RE = re.compile(r"\s+(?:[A-Z]\.?\s*){1,4}$")


def first_author_lastname(authors_field):
    """Best-effort extract of the first author's last name.

    Disambiguates "Lastname, Firstname" (one author, comma is internal)
    from "Lastname Initials, Lastname Initials" (multi-author, comma is
    separator) by looking at the pre-comma shape.

    Examples:
        "Smith, J; Doe, A"                 → "smith"
        "Khedr E"                          → "khedr"
        "Cervera M, Soekadar S, Ushiba J"  → "cervera"
        "John Smith and Jane Doe"          → "smith"
        "J. Smith, A. Doe"                 → "smith"
        "van der Berg JK"                  → "berg"
        "Mueller, H-G"                     → "mueller"
    """
    if not authors_field:
        return ""
    s = str(authors_field).strip()
    first = re.split(r"[;]| and ", s, maxsplit=1)[0].strip(" .,")
    if not first:
        return ""

    if "," in first:
        before, _, _ = first.partition(",")
        before = before.strip()
        if before and " " not in before:
            # "Lastname, Firstname" — single token before comma.
            return re.sub(r"[^A-Za-z]", "", before).lower()
        # Else: comma separates authors → keep only the first author chunk.
        first = before

    stripped = _TRAILING_INITIALS_RE.sub("", first).strip()
    if not stripped:
        return ""
    tokens = [t for t in re.split(r"\s+", stripped) if t]
    last = tokens[-1] if tokens else ""
    return re.sub(r"[^A-Za-z]", "", last).lower()


def norm_year(raw):
    if not raw:
        return ""
    s = str(raw).strip()
    m = re.search(r"(19|20)\d{2}", s)
    return m.group(0) if m else ""


# ----------------------------------------------------------------------
# Column mapping

def build_col_map(headers):
    """Return {canonical: source_header} mapping from raw header names."""
    out = {}
    seen_lower = {h.strip().lower(): h for h in headers if h is not None}
    for canon, aliases in COL_ALIASES.items():
        for alias in aliases:
            if alias in seen_lower:
                out[canon] = seen_lower[alias]
                break
    return out


def read_one_csv(path):
    """Return list[dict] of normalized rows. Each row also keeps `_source_file`."""
    src_db_from_name = path.stem  # e.g. "pubmed", "scopus"
    with open(path, newline="", encoding="utf-8-sig") as f:
        # Sniff delimiter (handle TSV / semicolon exports too)
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        headers = reader.fieldnames or []
        cmap = build_col_map(headers)
        rows = []
        for raw in reader:
            row = {
                "title": (raw.get(cmap.get("title", "")) or "").strip(),
                "authors": (raw.get(cmap.get("authors", "")) or "").strip(),
                "year": norm_year(raw.get(cmap.get("year", "")) or ""),
                "doi": norm_doi(raw.get(cmap.get("doi", "")) or ""),
                "pmid": norm_pmid(raw.get(cmap.get("pmid", "")) or ""),
                "abstract": (raw.get(cmap.get("abstract", "")) or "").strip(),
                "journal": (raw.get(cmap.get("journal", "")) or "").strip(),
                "source_db": (raw.get(cmap.get("source_db", "")) or src_db_from_name).strip(),
                "_source_file": path.name,
            }
            row["first_author"] = first_author_lastname(row["authors"])
            # Preserve any extra columns under their original keys (non-canonical)
            for h in headers:
                if h and h not in cmap.values() and h not in row:
                    val = (raw.get(h) or "").strip()
                    if val:
                        row[f"extra__{h}"] = val
            if not row["title"] and not row["doi"] and not row["pmid"]:
                # nothing identifying — skip silently
                continue
            rows.append(row)
    return rows


# ----------------------------------------------------------------------
# Dedup

def fuzzy_title_key(row):
    """Key used for fuzzy matching when DOI and PMID are both absent."""
    t = norm_text(row["title"])
    return (t, row["first_author"], row["year"])


def title_similar(a, b, threshold=0.92):
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def dedupe(rows, strict=False):
    """Cluster rows by identifier. Returns (clusters, log_entries).

    Each cluster is a list of source rows; the first row is the
    representative (richest record).
    """
    by_doi = defaultdict(list)
    by_pmid = defaultdict(list)
    no_id = []
    for r in rows:
        if r["doi"]:
            by_doi[r["doi"]].append(r)
        elif r["pmid"]:
            by_pmid[r["pmid"]].append(r)
        else:
            no_id.append(r)

    clusters = []
    log = []

    for doi, group in by_doi.items():
        clusters.append(("doi:" + doi, group))
        if len(group) > 1:
            log.append(("doi", doi, [r["_source_file"] for r in group]))

    for pmid, group in by_pmid.items():
        clusters.append(("pmid:" + pmid, group))
        if len(group) > 1:
            log.append(("pmid", pmid, [r["_source_file"] for r in group]))

    # No-ID rows: fuzzy cluster on (title, first_author, year)
    if no_id:
        if strict:
            for r in no_id:
                clusters.append(("noid:" + (r["title"][:40] or "?"), [r]))
        else:
            buckets = []  # list[(repr_row, [rows])]
            for r in no_id:
                key = fuzzy_title_key(r)
                placed = False
                for repr_row, group in buckets:
                    rk = fuzzy_title_key(repr_row)
                    if (
                        rk[1] == key[1]
                        and rk[2] == key[2]
                        and title_similar(rk[0], key[0])
                    ):
                        group.append(r)
                        placed = True
                        break
                if not placed:
                    buckets.append((r, [r]))
            for repr_row, group in buckets:
                clusters.append(("fuzzy:" + (repr_row["title"][:40] or "?"), group))
                if len(group) > 1:
                    log.append(("fuzzy", repr_row["title"][:80],
                                [r["_source_file"] for r in group]))

    return clusters, log


def pick_representative(group):
    """Return the row with the richest data (longest abstract wins, ties by DOI presence)."""
    return max(
        group,
        key=lambda r: (
            len(r["abstract"]),
            1 if r["doi"] else 0,
            1 if r["pmid"] else 0,
            len(r["title"]),
        ),
    )


def assign_slugs(records):
    """Generate <first-author>-<year> slugs with collision suffixes."""
    counts = defaultdict(int)
    for r in records:
        base = (r["first_author"] or "anon") + "-" + (r["year"] or "ny")
        counts[base] += 1
        n = counts[base]
        r["slug"] = base if n == 1 else f"{base}-{n}"


# ----------------------------------------------------------------------
# Output

def write_dedup_csv(records, out_path):
    # Detect extra__ columns across records
    extra_keys = sorted({k for r in records for k in r if k.startswith("extra__")})
    fieldnames = CANONICAL_COLS + extra_keys
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in records:
            row = {k: r.get(k, "") for k in fieldnames}
            w.writerow(row)


def write_log_md(log_entries, n_input, n_after, dropped_no_title, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Deduplication log",
        "",
        f"- Records read     : **{n_input}**",
        f"- Skipped (no ID)  : **{dropped_no_title}**",
        f"- Records kept     : **{n_after}**",
        f"- Duplicates merged: **{n_input - dropped_no_title - n_after}**",
        "",
        "## Duplicate clusters",
        "",
    ]
    if not log_entries:
        lines.append("_None._")
    else:
        for kind, key, files in log_entries:
            lines.append(f"- **{kind}** `{key}`")
            for f in files:
                lines.append(f"  - {f}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------
# CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("project", help="Path to project-review/<name>/")
    ap.add_argument("--strict", action="store_true",
                    help="Disable fuzzy title matching; only DOI + PMID dedup.")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    identified = project / "screening" / "identified"
    if not identified.is_dir():
        sys.exit(f"error: {identified} not found. Create it and drop your CSV exports there.")

    csvs = sorted(identified.glob("*.csv"))
    if not csvs:
        sys.exit(f"error: no .csv files in {identified}")

    rows = []
    for p in csvs:
        rows.extend(read_one_csv(p))

    n_input = sum(1 for p in csvs for _ in open(p, encoding="utf-8-sig")) - len(csvs)
    # subtract 1 header line per file
    dropped = n_input - len(rows)

    clusters, log_entries = dedupe(rows, strict=args.strict)

    records = []
    for _, group in clusters:
        rep = pick_representative(group)
        rec = dict(rep)
        rec["source_dbs"] = ",".join(sorted({r["source_db"] for r in group if r["source_db"]}))
        rec["merged_count"] = len(group)
        rec["merged_from"] = ",".join(sorted({r["_source_file"] for r in group}))
        records.append(rec)

    # Sort: by first_author then year for stable output
    records.sort(key=lambda r: (r["first_author"], r["year"], r["title"]))
    assign_slugs(records)

    dedup_csv = project / "screening" / "dedup.csv"
    write_dedup_csv(records, dedup_csv)

    log_md = project / "screening" / "reports" / "dedup-log.md"
    write_log_md(log_entries, n_input, len(records), dropped, log_md)

    print(f"✓ Read   {n_input:>5} records from {len(csvs)} CSV(s)")
    print(f"✓ Skipped{dropped:>5} (no title/DOI/PMID)")
    print(f"✓ Unique {len(records):>5} after dedup")
    print(f"✓ Wrote  {dedup_csv.relative_to(project.parent)}")
    print(f"✓ Wrote  {log_md.relative_to(project.parent)}")


if __name__ == "__main__":
    main()
