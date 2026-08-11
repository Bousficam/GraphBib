#!/usr/bin/env python3
"""Enrichit le frontmatter YAML des .md avec title, authors, journal, doi, year, cites.

Stratégie par fichier :
  1. parse le frontmatter existant (préserve source_pdf, backend, etc.)
  2. identifie le DOI DU DOCUMENT (voir ci-dessous)
  3. si DOI trouvé : appelle l'API Crossref pour récupérer les métadonnées canoniques
  4. fallback : métadonnées PDF (PyMuPDF) + premier H1 du MD
  5. parse la section References / Bibliography → liste de DOIs cités → cites: []
  6. réécrit le frontmatter (corps inchangé)

Identification du DOI (`pick_own_doi`)
--------------------------------------
Prendre le premier DOI du corps ne marche pas sur des PDF océrisés : la
mise en page fait remonter des DOI qui ne sont pas ceux du document, et
le fichier hérite alors du titre, des auteurs et de la revue d'un
*autre* papier. Trois causes observées sur ce corpus :

  - l'OCR hisse la liste de références (ou celle d'un article voisin
    imprimé sur la même page) au-dessus du texte ;
  - les commentaires et éditoriaux s'ouvrent sur « this article refers
    to <autre papier> (doi:...) » ;
  - le document n'imprime tout simplement pas son propre DOI.

D'où la stratégie, dans l'ordre :
  a. lire le titre du document (premier titre markdown *substantiel*,
     tous niveaux, hors boilerplate type « Abstract » ou « Corrections »)
     et l'interroger sur Crossref - route la plus directe et insensible
     à ce qu'a fait l'OCR ;
  b. sinon, collecter les DOI candidats en excluant le bloc de
     références et les lignes qui annoncent un autre travail, puis
     retenir celui dont le titre Crossref colle le mieux au titre lu ;
  c. sinon, garder le DOI vu mais SANS importer ses métadonnées, et
     poser `doi_confidence: low` dans le frontmatter pour audit.

Écrit enrich_report.json à la racine de DST (avec une liste
`low_confidence` des fichiers à revoir à la main).
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
import yaml
try:
    import pymupdf as fitz  # PyMuPDF >= 1.24 (new import name)
except ImportError:
    import fitz  # PyMuPDF < 1.24 (legacy import name)

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

# Lines that announce ANOTHER work rather than the present one. Editorials,
# commentaries and errata routinely open with such a line, and the DOI it
# carries belongs to the target of the comment, not to the comment.
FOREIGN_DOI_LINE_RE = re.compile(
    r"(refers?\s+to|comment(ary)?\s+on|in\s+response\s+to|reply\s+to|"
    r"erratum|corrigendum|correction\s+to|retraction\s+of|"
    r"this\s+article\s+is\s+a\s+commentary)",
    re.I,
)

# Headings that carry no bibliographic signal, so they must not be mistaken
# for the document's title when the OCR hoists them above the real title.
BOILERPLATE_HEADINGS = {
    "abstract", "introduction", "references", "bibliography", "glossary",
    "article info", "highlights", "keywords", "summary", "background",
    "methods", "method", "materials", "materials and methods", "results",
    "discussion", "conclusion", "conclusions", "acknowledgments",
    "acknowledgements", "corrections", "correction", "comment", "comments",
    "editorial", "erratum", "contents", "table of contents", "funding",
    "author contributions", "conflict of interest", "supplementary material",
    "figure", "table", "appendix", "notes", "part i", "part ii", "part iii",
    # Journal front matter that OCR often emits above the real title.
    "subject category", "subject categories", "subject areas", "subject area",
    "author for correspondence", "cite this article", "research",
    "electronic supplementary material", "data accessibility",
    "competing interests", "authors' contributions", "interface",
    "the royal society", "review", "mini review", "original research",
    "open access", "article info", "graphical abstract",
}

# A heading has to look like a title, not like a form label. "Subject
# Category" clears any character-count bar but is not a title; requiring a
# few words as well is what actually separates the two.
TITLE_MIN_WORDS = 3
TITLE_MIN_CHARS = 15

# Reuse the shared Crossref helpers (title matching + on-disk cache) rather
# than duplicating them here.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
try:
    from crossref import (  # noqa: E402
        crossref_search,
        load_cache,
        save_cache,
        norm_title,
        title_overlap,
        title_similarity,
    )
    _HAVE_SHARED_CROSSREF = True
except Exception:  # pragma: no cover - tools/ not importable
    _HAVE_SHARED_CROSSREF = False

# A candidate DOI is accepted as "the document's own" when its Crossref
# title matches the title we read off the document this closely.
TITLE_MATCH_MIN = 0.60


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


def body_before_references(body: str) -> str:
    """Return the body with the reference list stripped off.

    DOIs living in the reference list are, by construction, citations. OCR
    frequently hoists that list (or a neighbouring article's list on the
    same printed page) above the body text, which is how a cited work's
    DOI ends up being the first one in reading order.
    """
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith("#"):
            continue
        heading = s.lstrip("#").strip().lower().rstrip(":.")
        if any(heading == h or heading.startswith(h + " ") for h in REF_HEADERS):
            return "\n".join(lines[:i])
    return body


def document_title(body: str, pdf_meta: dict, stem: str) -> str | None:
    """Best guess at the title of the document itself.

    Takes the first *substantive* markdown heading of any level - the
    plain `first_h1` misses titles the OCR emitted as `##`, and picks up
    boilerplate such as `# Corrections` or `# Abstract` when the OCR puts
    those first.
    """
    for ln in body.splitlines():
        s = ln.strip()
        if not s.startswith("#"):
            continue
        h = s.lstrip("#").strip().strip("*_").rstrip(":.")
        key = h.lower().rstrip(":.")
        if not h or key in BOILERPLATE_HEADINGS:
            continue
        if len(h) < TITLE_MIN_CHARS or len(h.split()) < TITLE_MIN_WORDS:
            continue
        return h
    meta_title = (pdf_meta.get("title") or "").strip()
    if len(meta_title) >= 15 and meta_title.lower() != stem.lower():
        return meta_title
    return None


def own_doi_candidates(body: str, page1: str) -> list[str]:
    """Ordered candidates for the document's OWN doi, best guess first.

    Excludes the reference list and any line that announces another work
    (`refers to`, `comment on`, `erratum`...). Falls back to the raw body
    last, so a document whose only DOI sits inside its reference block is
    no worse off than before.
    """
    def harvest(text: str) -> list[str]:
        out = []
        for ln in text.splitlines():
            if FOREIGN_DOI_LINE_RE.search(ln):
                continue
            for m in DOI_RE.finditer(ln):
                out.append(m.group(0).rstrip(".,;)"))
        return out

    ordered = harvest(body_before_references(body)) + harvest(page1) + harvest(body)
    seen, cands = set(), []
    for d in ordered:
        k = d.lower()
        if k not in seen:
            seen.add(k)
            cands.append(d)
    return cands


def pick_own_doi(body: str, page1: str, pdf_meta: dict, stem: str):
    """Resolve the document's own DOI. Returns (metadata|None, doi|None, confident).

    Strategy, in order:
      1. look the title up at Crossref - the most direct route, and immune
         to whatever the OCR did to the body;
      2. otherwise score each candidate DOI's Crossref title against the
         title we read off the document, and keep the best match;
      3. otherwise fall back to the first candidate that resolves at all,
         reporting low confidence so the run can be audited.
    """
    title = document_title(body, pdf_meta, stem)
    cands = own_doi_candidates(body, page1)

    if title and _HAVE_SHARED_CROSSREF:
        cache = load_cache()
        try:
            found = crossref_search(title, cache)
        finally:
            save_cache(cache)
        if found:
            cr = crossref(found)
            if cr and cr.get("title") and _title_matches(title, cr["title"]):
                return cr, found, True

    scored = []
    for d in cands[:6]:
        cr = crossref(d)
        time.sleep(0.05)  # politesse API Crossref
        if not cr:
            continue
        if title and cr.get("title"):
            score = _title_score(title, cr["title"])
            scored.append((score, d, cr))
        else:
            scored.append((0.0, d, cr))
    if not scored:
        return None, (cands[0] if cands else None), False

    if not title:
        # No title to arbitrate with. A single candidate is almost always
        # the document's own DOI; several means we are guessing, and a
        # guess must not import a title/authors/journal that would then
        # rename the document after some work it merely cites.
        if len(scored) == 1:
            return scored[0][2], scored[0][1], True
        return None, scored[0][1], False

    best = max(scored, key=lambda t: t[0])
    if best[0] >= TITLE_MATCH_MIN:
        return best[2], best[1], True

    # Nothing matched the title well enough. Do NOT hand back the
    # best-scoring candidate: when the title we read is itself wrong (a
    # form label the OCR hoisted above the real title, say), every score
    # is noise and "highest score" just picks an arbitrary citation. Fall
    # back to the first candidate in filtered reading order, which is what
    # a document prints of its own DOI, and flag the result.
    return None, scored[0][1], False


def _title_score(a: str, b: str) -> float:
    if not _HAVE_SHARED_CROSSREF:
        return 1.0 if a.strip().lower() == b.strip().lower() else 0.0
    return max(title_similarity(a, b), title_overlap(a, b))


def _title_matches(a: str, b: str) -> bool:
    return _title_score(a, b) >= TITLE_MATCH_MIN


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

    cr, doi, confident = pick_own_doi(body, page1, pdf_meta, md_path.stem)

    # A low-confidence guess must never overwrite a DOI that is already in
    # the frontmatter: re-running the enrichment has to be safe on a corpus
    # whose metadata was curated by hand.
    prev_doi = (str(fm.get("doi") or "")).strip()
    if not confident and prev_doi:
        cr, doi = None, prev_doi
    elif prev_doi and doi and prev_doi.lower() == doi.lower():
        # Same DOI, different casing: DOIs are case-insensitive, so keep the
        # form already on disk and leave the file byte-identical. Re-running
        # the pipeline over the corpus must not dirty every file.
        doi = prev_doi
        if cr:
            cr = dict(cr, doi=prev_doi)

    out = dict(fm)
    out.pop("doi_confidence", None)
    if doi and not confident:
        # Flag whether or not we managed to import metadata: the case where
        # we could NOT is precisely the one a human most needs to re-check.
        out["doi_confidence"] = "low"
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

    rep = {"crossref_ok": [], "doi_only": [], "no_doi": [], "with_cites": [],
           "low_confidence": [], "errors": []}
    for md in mds:
        rel = str(md.relative_to(dst))
        try:
            fm = enrich(md)
            if fm.get("doi_confidence") == "low":
                rep["low_confidence"].append({"file": rel, "doi": fm.get("doi")})
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
        "low_confidence": len(rep["low_confidence"]),
        "errors": len(rep["errors"]),
    }
    (dst / "enrich_report.json").write_text(
        json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"=== RÉSUMÉ === {rep['summary']}")


if __name__ == "__main__":
    main()
