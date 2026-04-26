"""
Automatic detection of PDF extraction artifacts in keyword lists.
Also provides a clean_text() method to strip artifacts from raw PDF text
before TF-IDF processing.
"""
from __future__ import annotations

import re
from typing import Dict, Tuple

# ── Confirmed artifact patterns ─────────────────────────────────────────────
# Patterns here are unambiguous: these are never valid keywords.
_CONFIRMED: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^cid$", re.I),                   "Artefact PDF : encodage 'cid'"),
    (re.compile(r"cid\s*:?\s*\d+", re.I),          "Artefact PDF : 'cid:N'"),
    (re.compile(r"^\d+$"),                          "Token purement numérique"),
    (re.compile(r"^[a-zà-ü\-]{1,2}$"),             "Token trop court (≤ 2 car.)"),
    (re.compile(r"^(fi+|fl+|ffi+|ffl+|ff)$"),      "Ligature typographique"),
    (re.compile(r"^[^a-záàâäéèêëíìîïóòôöúùûüñ]+$"),"Aucune lettre alphabétique"),
]

# ── Suspected artifact patterns ──────────────────────────────────────────────
# Lower confidence: shown to user for review.
_SUSPECTED: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\d"),                             "Contient des chiffres"),
    (re.compile(r"^[a-zà-ü\-]{3}$"),               "Très court (3 car.)"),
    (re.compile(r"[^a-záàâäéèêëíìîïóòôöúùûüñ\s\-]"), "Caractères spéciaux"),
]

_NUMERIC_RATIO = 0.45        # >45 % de chiffres → artefact confirmé
_HIGH_FREQ_RATIO = 0.65      # présent dans >65 % des docs → suspect générique

# ── Raw-text cleanup regexes ────────────────────────────────────────────────
_RAW_PATTERNS = [
    re.compile(r"\(cid:\d+\)", re.I),
    re.compile(r"cid:\d+", re.I),
    re.compile(r"\bfi\b|\bfl\b|\bffi\b|\bffl\b|\bff\b"),
    re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"),  # control chars
]


class KeywordCleaner:
    """Detect and remove PDF extraction artifacts from keyword lists."""

    def detect(
        self,
        keywords: Dict[str, int],
        n_docs: int,
    ) -> Dict[str, Dict[str, str]]:
        """
        Returns:
            {
                "confirmed": {kw: reason},   # automatically reject
                "suspected": {kw: reason},   # ask user
            }
        """
        confirmed: Dict[str, str] = {}
        suspected: Dict[str, str] = {}

        for kw, freq in keywords.items():
            if reason := self._confirmed_reason(kw):
                confirmed[kw] = reason
                continue

            # High-frequency generic token
            if n_docs > 0 and freq / n_docs > _HIGH_FREQ_RATIO:
                suspected[kw] = (
                    f"Présent dans {freq}/{n_docs} docs "
                    f"({round(100 * freq / n_docs)}%) — très générique"
                )
                continue

            if reason := self._suspected_reason(kw):
                suspected[kw] = reason

        return {"confirmed": confirmed, "suspected": suspected}

    def clean_text(self, text: str) -> str:
        """Strip cid:N tokens and encoding artifacts from raw extracted text."""
        for pat in _RAW_PATTERNS:
            text = pat.sub(" ", text)
        return text

    # ------------------------------------------------------------------
    @staticmethod
    def _confirmed_reason(kw: str) -> str:
        for pat, reason in _CONFIRMED:
            if pat.search(kw):
                return reason
        # Numeric-ratio check
        if len(kw) >= 2:
            ratio = sum(c.isdigit() for c in kw) / len(kw)
            if ratio > _NUMERIC_RATIO:
                return f"Token majoritairement numérique ({round(ratio*100)}% chiffres)"
        return ""

    @staticmethod
    def _suspected_reason(kw: str) -> str:
        for pat, reason in _SUSPECTED:
            if pat.search(kw):
                return reason
        return ""
