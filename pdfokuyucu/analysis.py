from __future__ import annotations

import difflib
import re
from collections import Counter

from .config import STOP_WORDS
from .models import PdfDocument


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if len(sentence.strip()) > 30
    ]


def keywords(text: str, limit: int = 10) -> list[str]:
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{4,}", text.lower())
    filtered_words = [word for word in words if word not in STOP_WORDS]
    return [word for word, _ in Counter(filtered_words).most_common(limit)]


def summarize(text: str, max_sentences: int = 5) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return "Özet çıkarılabilecek yeterli metin bulunamadı."

    key_terms = set(keywords(text, limit=24))
    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        sentence_words = set(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{4,}", sentence.lower()))
        score = len(sentence_words & key_terms)
        if index < 3:
            score += 2
        scored.append((score, index, sentence))

    selected = sorted(scored, key=lambda item: (-item[0], item[1]))[:max_sentences]
    return " ".join(sentence for _, _, sentence in sorted(selected, key=lambda item: item[1]))


def page_summaries(document: PdfDocument, max_sentences: int = 2) -> list[dict[str, object]]:
    return [
        {"page": index, "summary": summarize(text, max_sentences)}
        for index, text in enumerate(document.text_by_page, start=1)
    ]


def section_summaries(document: PdfDocument, pages_per_section: int = 5) -> list[dict[str, object]]:
    sections = []
    for start in range(0, document.page_count, pages_per_section):
        end = min(start + pages_per_section, document.page_count)
        text = "\n".join(document.text_by_page[start:end])
        sections.append({"title": f"Sayfa {start + 1}-{end}", "summary": summarize(text, 3)})
    return sections


def comparison_result(left: PdfDocument, right: PdfDocument, keyword_limit: int) -> dict[str, object]:
    diff = list(
        difflib.unified_diff(
            left.full_text.splitlines(),
            right.full_text.splitlines(),
            fromfile=left.filename,
            tofile=right.filename,
            lineterm="",
        )
    )
    return {
        "left": left.filename,
        "right": right.filename,
        "diff": diff[:500],
        "common_keywords": sorted(set(keywords(left.full_text, keyword_limit)) & set(keywords(right.full_text, keyword_limit))),
    }
