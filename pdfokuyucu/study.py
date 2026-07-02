from __future__ import annotations

import re
from collections import Counter

from .analysis import keywords, split_sentences, summarize
from .models import PdfDocument


WORD_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{4,}", re.UNICODE)


def normalize_term(term: str) -> str:
    return term.strip().lower()


def sentence_terms(sentence: str, key_terms: list[str]) -> list[str]:
    lowered = sentence.lower()
    return [term for term in key_terms if normalize_term(term) in lowered]


def clean_sentence(sentence: str, limit: int = 260) -> str:
    sentence = re.sub(r"\s+", " ", sentence).strip()
    if len(sentence) <= limit:
        return sentence
    return sentence[: limit - 3].rsplit(" ", 1)[0] + "..."


def pages_for_term(document: PdfDocument, term: str) -> list[int]:
    normalized = normalize_term(term)
    return [
        page
        for page, text in enumerate(document.text_by_page, start=1)
        if normalized in text.lower()
    ][:3]


def ranked_study_sentences(document: PdfDocument, key_terms: list[str], limit: int = 18) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for page, page_text in enumerate(document.text_by_page, start=1):
        for sentence in split_sentences(page_text):
            terms = sentence_terms(sentence, key_terms)
            if not terms:
                continue
            score = len(set(terms)) * 2 + min(len(sentence) // 80, 3)
            items.append(
                {
                    "page": page,
                    "sentence": clean_sentence(sentence),
                    "terms": terms,
                    "score": score,
                }
            )
    return sorted(items, key=lambda item: (-int(item["score"]), int(item["page"])))[:limit]


def build_quiz(study_sentences: list[dict[str, object]], key_terms: list[str], limit: int = 5) -> list[dict[str, object]]:
    quiz = []
    used_terms: set[str] = set()
    for item in study_sentences:
        terms = [term for term in item["terms"] if term not in used_terms]
        if not terms:
            continue
        answer = str(terms[0])
        distractors = [term for term in key_terms if term != answer][:3]
        options = [answer, *distractors]
        used_terms.add(answer)
        quiz.append(
            {
                "question": f"Metne göre bu açıklama en çok hangi kavramla ilişkilidir?",
                "prompt": item["sentence"],
                "answer": answer,
                "options": options[:4],
                "page": item["page"],
            }
        )
        if len(quiz) >= limit:
            break
    return quiz


def build_flashcards(study_sentences: list[dict[str, object]], limit: int = 6) -> list[dict[str, object]]:
    cards = []
    used_terms: set[str] = set()
    for item in study_sentences:
        for term in item["terms"]:
            if term in used_terms:
                continue
            used_terms.add(term)
            cards.append(
                {
                    "front": term,
                    "back": item["sentence"],
                    "page": item["page"],
                }
            )
            break
        if len(cards) >= limit:
            break
    return cards


def build_cloze_cards(study_sentences: list[dict[str, object]], limit: int = 5) -> list[dict[str, object]]:
    cloze_cards = []
    used_terms: set[str] = set()
    for item in study_sentences:
        term = next((candidate for candidate in item["terms"] if candidate not in used_terms), "")
        if not term:
            continue
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        text = pattern.sub("_____", str(item["sentence"]), count=1)
        if text == item["sentence"]:
            continue
        used_terms.add(term)
        cloze_cards.append(
            {
                "text": text,
                "answer": term,
                "page": item["page"],
            }
        )
        if len(cloze_cards) >= limit:
            break
    return cloze_cards


def build_review_plan(document: PdfDocument, key_terms: list[str]) -> list[dict[str, object]]:
    page_scores = []
    for page, page_text in enumerate(document.text_by_page, start=1):
        page_terms = sentence_terms(page_text, key_terms)
        if not page_terms:
            continue
        page_scores.append((len(page_terms), page, Counter(page_terms).most_common(3)))

    review_pages = sorted(page_scores, key=lambda item: (-item[0], item[1]))[:3]
    plan = [
        {
            "title": "Hızlı ısınma",
            "detail": "Belge özetini oku ve anahtar kavramları kendi cümlelerinle tekrar et.",
            "duration": "5 dk",
        }
    ]
    for _, page, common_terms in review_pages:
        terms = ", ".join(term for term, _ in common_terms)
        plan.append(
            {
                "title": f"Sayfa {page} odak tekrarı",
                "detail": f"Bu sayfadaki {terms} kavramlarını açıklamaya çalış.",
                "duration": "8 dk",
            }
        )
    plan.append(
        {
            "title": "Kapanış testi",
            "detail": "Quiz ve boşluk doldurma kartlarını cevaplayıp yanlışlarını notlara ekle.",
            "duration": "7 dk",
        }
    )
    return plan


def build_study_mode(document: PdfDocument, keyword_limit: int = 12) -> dict[str, object]:
    key_terms = keywords(document.full_text, keyword_limit)
    study_sentences = ranked_study_sentences(document, key_terms)
    fallback_summary = summarize(document.full_text, 4)
    if not study_sentences and fallback_summary:
        study_sentences = [{"page": 1, "sentence": fallback_summary, "terms": key_terms[:2], "score": 1}]

    return {
        "quiz": build_quiz(study_sentences, key_terms),
        "flashcards": build_flashcards(study_sentences),
        "cloze": build_cloze_cards(study_sentences),
        "review_plan": build_review_plan(document, key_terms),
        "focus_terms": key_terms[:8],
        "estimated_minutes": max(12, min(45, document.word_count // 180 + 10)),
    }
