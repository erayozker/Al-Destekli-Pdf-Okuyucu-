from __future__ import annotations

import re

from .models import PdfDocument


def search_terms(query: str, mode: str) -> list[str]:
    cleaned = query.strip()
    if not cleaned:
        return []
    if mode == "exact":
        return [cleaned]
    return [term for term in re.split(r"\s+", cleaned) if term]


def compile_term(term: str, case_sensitive: bool, whole_word: bool) -> re.Pattern[str]:
    escaped = re.escape(term)
    if whole_word:
        escaped = rf"(?<!\w){escaped}(?!\w)"
    return re.compile(escaped, 0 if case_sensitive else re.IGNORECASE)


def highlight_terms(text: str, terms: list[str], case_sensitive: bool, whole_word: bool) -> str:
    highlighted = text
    for term in sorted(terms, key=len, reverse=True):
        highlighted = compile_term(term, case_sensitive, whole_word).sub(
            r"[[HIGHLIGHT]]\g<0>[[/HIGHLIGHT]]",
            highlighted,
        )
    return highlighted


def search_document(document: PdfDocument, options: dict[str, object]) -> list[dict[str, object]]:
    terms = search_terms(str(options["query"]), str(options["search_mode"]))
    if not terms:
        return []

    case_sensitive = bool(options["case_sensitive"])
    whole_word = bool(options["whole_word"])
    mode = str(options["search_mode"])
    page_from = max(1, int(options["page_from"]))
    page_to = min(document.page_count, int(options["page_to"]))
    patterns = [compile_term(term, case_sensitive, whole_word) for term in terms]
    results: list[dict[str, object]] = []

    for page_index, page_text in enumerate(document.text_by_page, start=1):
        if page_index < page_from or page_index > page_to:
            continue
        per_term_matches = [list(pattern.finditer(page_text)) for pattern in patterns]
        if mode == "all" and not all(per_term_matches):
            continue
        matches = [match for matches_for_term in per_term_matches for match in matches_for_term]
        if not matches:
            continue

        first_match = sorted(matches, key=lambda item: item.start())[0]
        start = max(first_match.start() - 90, 0)
        end = min(first_match.end() + 150, len(page_text))
        snippet = re.sub(r"\s+", " ", page_text[start:end]).strip()
        if start > 0:
            snippet = "... " + snippet
        if end < len(page_text):
            snippet += " ..."
        results.append(
            {
                "page": page_index,
                "count": len(matches),
                "snippet": highlight_terms(snippet, terms, case_sensitive, whole_word),
            }
        )
    return results
