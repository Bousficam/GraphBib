from pathlib import Path
from typing import Dict, List, Optional, Set

SUPPORTED_FORMATS: Set[str] = {".pdf", ".bib", ".md", ".txt"}


class FileScanner:
    def __init__(self, root_path: str, formats: Optional[Set[str]] = None):
        self.root = Path(root_path).resolve()
        self.formats = formats or SUPPORTED_FORMATS

    def scan(self) -> List[Path]:
        files = [
            p
            for p in self.root.rglob("*")
            if p.is_file() and p.suffix.lower() in self.formats
        ]
        return sorted(files)

    def stats(self, paths: List[Path]) -> Dict:
        by_format: Dict[str, int] = {}
        for p in paths:
            ext = p.suffix.lower()
            by_format[ext] = by_format.get(ext, 0) + 1
        return {"total": len(paths), "by_format": by_format, "root": str(self.root)}
