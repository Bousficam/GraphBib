#!/usr/bin/env python3
"""Enrichit le frontmatter YAML des .md avec title, authors, journal, doi, year, cites.

Stratégie par fichier :
  1. parse le frontmatter existant (préserve source_pdf, backend, etc.)
  2. cherche un DOI (regex) dans le corps du MD puis dans la 1re page du PDF source
  3. si DOI trouvé : appelle l'API Crossref pour récupérer les métadonnées canoniques
  4. fallback : métadonnées PDF (PyMuPDF) + premier H1 du MD
  5. parse la section References / Bibliography → liste de DOIs cités → cites: []
  6. réécrit le frontmatter (corps inchangé)

Écrit enrich_report.json à la racine de DST.
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
import yaml
import fitz  # PyMuPDF, dépendance de marker / pymupdf4llm

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
REF_HEADERS = (
    "references",
    "bibliography",
    "cited works",
    "works cited",
    "literature cited",
    "réferences",
    "références",
)


def parse_fm(text: str):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5:]
            except Exception:
                pass
    return {}, text


def first_h1(body: str):
    for ln in body.splitlines():
        if ln.lstrip().startswith("# "):
            return ln.lstrip("# ").strip()
    return None


def extract_references_block(body: str) -> str:
    """Return the text after the first References / Bibliography heading."""
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith("#"):
            continue
        heading = s.lstrip("#").strip().lower().rstrip(":.")
        if any(heading == h or heading.startswith(h + " ") for h in REF_HEADERS):
            return "\n".join(lines[i + 1:])
    return ""


def extract_cited_dois(body: str, own_doi: str | None) -> list[str]:
    refs = extract_references_block(body)
    if not refs:
        return []
    seen: set[str] = set()
    own = (own_doi or "").lower()
    out: list[str] = []
    for m in DOI_RE.finditer(refs):
        d = m.group(0).rstrip(".,;)").lower()
        if d == own or d in seen:
            continue
        seen.add(d)
        out.append(d)
    return out


def pdf_first_page(p: Path):
    try:
        with fitz.open(str(p)) as d:
            meta = d.metadata or {}
            page1 = d[0].get_text() if d.page_count else ""
        return meta, page1
    except Exception:
        return {}, ""


def crossref(doi: str):
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{quote(doi, safe='/:')}",
            timeout=10,
            headers={"User-Agent": "graphbib/0.1 (mailto:contact@example.com)"},
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
            "doi": doi,
        }
    except Exception:
        return None


def enrich(md_path: Path):
    text = md_path.read_text(encoding="utf-8")
    fm, body = parse_fm(text)

    pdf_path = Path(fm.get("source_pdf", "")) if fm.get("source_pdf") else None
    pdf_meta, page1 = pdf_first_page(pdf_path) if pdf_path and pdf_path.exists() else ({}, "")

    doi_match = DOI_RE.search(body) or DOI_RE.search(page1)
    doi = doi_match.group(0).rstrip(".,;)") if doi_match else None

    cr = crossref(doi) if doi else None
    time.sleep(0.05)  # politesse API Crossref

    out = dict(fm)
    if cr:
        out.update({k: v for k, v in cr.items() if v})
    else:
        if doi:
            out["doi"] = doi
        if not out.get("title"):
            out["title"] = (
                (pdf_meta.get("title") or "").strip()
                or first_h1(body)
                or md_path.stem
            )
        if not out.get("authors") and pdf_meta.get("author"):
            out["authors"] = [
                a.strip() for a in re.split(r"[;,]", pdf_meta["author"]) if a.strip()
            ]

    cites = extract_cited_dois(body, out.get("doi"))
    if cites:
        out["cites"] = cites

    new_fm = yaml.safe_dump(out, allow_unicode=True, sort_keys=False).strip()
    md_path.write_text(f"---\n{new_fm}\n---\n\n{body.lstrip()}", encoding="utf-8")
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: enrich_frontmatter.py DST")

    dst = Path(sys.argv[1]).expanduser().resolve()
    skip_names = {"marker.log", "fallback.log"}
    mds = [
        p for p in sorted(dst.rglob("*.md"))
        if p.name not in skip_names
    ]
    print(f"{len(mds)} fichiers MD à enrichir")

    rep = {"crossref_ok": [], "doi_only": [], "no_doi": [], "with_cites": [], "errors": []}
    for md in mds:
        rel = str(md.relative_to(dst))
        try:
            fm = enrich(md)
            if fm.get("journal"):
                rep["crossref_ok"].append({"file": rel, "doi": fm.get("doi")})
            elif fm.get("doi"):
                rep["doi_only"].append({"file": rel, "doi": fm["doi"]})
            else:
                rep["no_doi"].append(rel)
            n_cites = len(fm.get("cites") or [])
            if n_cites:
                rep["with_cites"].append({"file": rel, "n": n_cites})
        except Exception as e:
            rep["errors"].append({"file": rel, "error": repr(e)})

    rep["summary"] = {
        "total": len(mds),
        "crossref_ok": len(rep["crossref_ok"]),
        "doi_only": len(rep["doi_only"]),
        "no_doi": len(rep["no_doi"]),
        "with_cites": len(rep["with_cites"]),
        "errors": len(rep["errors"]),
    }
    (dst / "enrich_report.json").write_text(
        json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"=== RÉSUMÉ === {rep['summary']}")


if __name__ == "__main__":
    main()
