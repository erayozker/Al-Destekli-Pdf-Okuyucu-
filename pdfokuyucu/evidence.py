from __future__ import annotations

import re

from .ai_service import SourceChunk
from .config import STOP_WORDS
from .models import PdfDocument
from .search import highlight_terms


TERM_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{4,}", re.UNICODE)


def question_terms(question: str) -> list[str]:
    terms = []
    seen: set[str] = set()
    for term in TERM_RE.findall(question.lower()):
        if term in STOP_WORDS or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms[:8]


def snippet_for_terms(text: str, terms: list[str], limit: int = 360) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""
    lowered = compact.lower()
    matches = [lowered.find(term.lower()) for term in terms if term and lowered.find(term.lower()) >= 0]
    start = max(min(matches) - 110, 0) if matches else 0
    end = min(start + limit, len(compact))
    snippet = compact[start:end].strip()
    if start > 0:
        snippet = "... " + snippet
    if end < len(compact):
        snippet += " ..."
    return highlight_terms(snippet, terms, False, False) if terms else snippet


def build_evidence_cards(
    document: PdfDocument,
    question: str,
    chunks: list[SourceChunk],
    limit: int = 3,
) -> list[dict[str, object]]:
    terms = question_terms(question)
    cards = []
    used_pages: set[int] = set()
    for chunk in chunks:
        if chunk.page in used_pages and len(cards) >= 1:
            continue
        used_pages.add(chunk.page)
        page_text = document.text_by_page[chunk.page - 1] if 0 < chunk.page <= document.page_count else chunk.text
        cards.append(
            {
                "page": chunk.page,
                "score": chunk.score,
                "snippet": snippet_for_terms(chunk.text or page_text, terms),
                "page_excerpt": snippet_for_terms(page_text, terms, 260),
            }
        )
        if len(cards) >= limit:
            break
    return cards
