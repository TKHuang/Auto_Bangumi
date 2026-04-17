"""Title normalization for fallback (non-Mikan) series identity matching.

Produces a (normalized_title, cour_part) tuple so that:
  - Traditional / Simplified Chinese variants collapse
  - Full-width / half-width punctuation collapse
  - Season markers (第N季 / Season N / SN) are stripped (kept in season field)
  - Cour markers (后半部分 / Part N / Cour N) are extracted as a separate field
  - Brackets, punctuation and whitespace are dropped

Used by SeriesRepository.get_by_fallback() when no Mikan ID is available.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from opencc import OpenCC

_cc_t2s = OpenCC("t2s")

_SEASON_PATTERNS = [
    r"第\s*[0-9一二三四五六七八九十百]+\s*[季期]",
    r"[Ss]eason\s*\d+",
    r"\bS\d+\b",
    r"\bSP\b",
    r"\bOVA\b",
    r"\bOAD\b",
]

_COUR_PATTERNS: list[tuple[str, str]] = [
    (r"后半部分|後半部分|后半|後半", "latter"),
    (r"前半部分|前半部分|前半", "former"),
    (r"第\s*[0-9一二]+\s*部分", "part"),
    (r"[Pp]art\s*\d+", "part"),
    (r"[Cc]our\s*\d+", "cour"),
]


def normalize_title(raw: str) -> tuple[str, Optional[str]]:
    """Return (normalized_title, cour_part).

    cour_part is one of 'latter' | 'former' | 'part' | 'cour' | None.
    """
    s = unicodedata.normalize("NFKC", raw)
    s = _cc_t2s.convert(s)

    cour: Optional[str] = None
    for pattern, kind in _COUR_PATTERNS:
        if re.search(pattern, s):
            cour = kind
            s = re.sub(pattern, "", s)
            break

    for pattern in _SEASON_PATTERNS:
        s = re.sub(pattern, "", s)

    # Keep: CJK unified (U+4E00-U+9FFF), Hiragana+Katakana (U+3040-U+30FF),
    # word chars (Latin letters + digits + underscore). Drop everything else.
    s = re.sub(r"[^\w\u4e00-\u9fff\u3040-\u30ff]+", "", s)
    return s.lower().strip(), cour
