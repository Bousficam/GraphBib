from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Document:
    path: str
    filename: str
    title: str
    authors: List[str]
    year: Optional[int]
    abstract: str
    full_text: str
    format: str  # pdf | bib | md | txt
    keywords: List[str] = field(default_factory=list)
    keyword_scores: Dict[str, float] = field(default_factory=dict)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    # Populated by Step 2 clustering
    clusters: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "filename": self.filename,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "abstract": self.abstract[:500] if self.abstract else "",
            "format": self.format,
            "keywords": self.keywords,
            "keyword_scores": self.keyword_scores,
            "clusters": self.clusters,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        return cls(
            path=d.get("path", ""),
            filename=d.get("filename", ""),
            title=d.get("title", ""),
            authors=d.get("authors", []),
            year=d.get("year"),
            abstract=d.get("abstract", ""),
            full_text="",  # not persisted (too large)
            format=d.get("format", ""),
            keywords=d.get("keywords", []),
            keyword_scores=d.get("keyword_scores", {}),
            raw_metadata={},
            clusters=d.get("clusters", []),
        )
