import re
from pathlib import Path
from typing import List, Optional

from .models import Document


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _guess_title(text: str, fallback: str) -> str:
    for line in text.split("\n")[:10]:
        line = line.strip()
        if 15 < len(line) < 300 and not line.lower().startswith(("http", "doi", "arxiv", "©")):
            return line
    return fallback


class TextExtractor:
    """Extract text and basic metadata from PDF, BibTeX, Markdown, and TXT files."""

    def extract(self, path: Path) -> List[Document]:
        ext = path.suffix.lower()
        try:
            if ext == ".pdf":
                doc = self._pdf(path)
                return [doc] if doc else []
            if ext == ".bib":
                return self._bib(path)
            if ext == ".md":
                return [self._md(path)]
            if ext == ".txt":
                return [self._txt(path)]
        except Exception as exc:
            return [
                Document(
                    path=str(path),
                    filename=path.name,
                    title=path.stem,
                    authors=[],
                    year=None,
                    abstract="",
                    full_text="",
                    format=ext.lstrip("."),
                    raw_metadata={"error": str(exc)},
                )
            ]
        return []

    # ------------------------------------------------------------------
    def _pdf(self, path: Path) -> Optional[Document]:
        import pdfplumber  # optional dependency, imported lazily

        pages_text: List[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages[:40]:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
        full_text = _clean("\n".join(pages_text))
        return Document(
            path=str(path),
            filename=path.name,
            title=_guess_title(full_text, path.stem),
            authors=[],
            year=None,
            abstract=full_text[:800],
            full_text=full_text,
            format="pdf",
        )

    # ------------------------------------------------------------------
    def _bib(self, path: Path) -> List[Document]:
        import bibtexparser  # optional dependency

        with open(path, encoding="utf-8", errors="replace") as fh:
            db = bibtexparser.load(fh)

        docs: List[Document] = []
        for entry in db.entries:
            authors_raw = entry.get("author", "")
            authors = [a.strip() for a in re.split(r"\band\b", authors_raw) if a.strip()]

            year_raw = entry.get("year", "")
            year = int(year_raw) if str(year_raw).isdigit() else None

            keywords_raw = entry.get("keywords", "")
            predefined_kw = [k.strip() for k in re.split(r"[,;]", keywords_raw) if k.strip()]

            title = _clean(entry.get("title", entry.get("ID", path.stem)))
            abstract = _clean(entry.get("abstract", ""))
            full_text = _clean(f"{title} {abstract}")

            docs.append(
                Document(
                    path=str(path),
                    filename=f"{entry.get('ID', 'unknown')}.bib",
                    title=title,
                    authors=authors,
                    year=year,
                    abstract=abstract,
                    full_text=full_text,
                    format="bib",
                    raw_metadata={
                        "bibtex_id": entry.get("ID", ""),
                        "entry_type": entry.get("ENTRYTYPE", ""),
                        "predefined_keywords": predefined_kw,
                    },
                )
            )
        return docs

    # ------------------------------------------------------------------
    def _md(self, path: Path) -> Document:
        content = path.read_text(encoding="utf-8", errors="replace")
        meta: dict = {}
        body = content

        if content.startswith("---"):
            try:
                import yaml

                parts = content.split("---", 2)
                if len(parts) >= 3:
                    meta = yaml.safe_load(parts[1]) or {}
                    body = parts[2]
            except Exception:
                pass

        title = str(meta.get("title") or _guess_title(body, path.stem))

        authors_raw = meta.get("authors", meta.get("author", []))
        if isinstance(authors_raw, str):
            authors_raw = [authors_raw]

        year_raw = meta.get("year")
        year = int(str(year_raw)) if year_raw and str(year_raw).isdigit() else None

        predefined_kw = meta.get("keywords", meta.get("tags", []))
        if isinstance(predefined_kw, str):
            predefined_kw = [predefined_kw]

        clean_body = _clean(re.sub(r"[#*`\[\]()>~]", " ", body))
        full_text = _clean(f"{title} {clean_body}")

        return Document(
            path=str(path),
            filename=path.name,
            title=title,
            authors=list(authors_raw),
            year=year,
            abstract=full_text[:500],
            full_text=full_text,
            format="md",
            raw_metadata={"frontmatter": meta, "predefined_keywords": list(predefined_kw)},
        )

    # ------------------------------------------------------------------
    def _txt(self, path: Path) -> Document:
        content = path.read_text(encoding="utf-8", errors="replace")
        full_text = _clean(content)
        return Document(
            path=str(path),
            filename=path.name,
            title=_guess_title(full_text, path.stem),
            authors=[],
            year=None,
            abstract=full_text[:500],
            full_text=full_text,
            format="txt",
        )
