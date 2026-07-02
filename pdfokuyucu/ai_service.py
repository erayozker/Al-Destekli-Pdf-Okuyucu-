from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass

from .config import AI_SYNC_MAX_CHARS, AI_SYNC_MAX_PAGES
from .models import PdfDocument
from .repository import get_embedding_cache, save_embedding_cache


AI_SUMMARY_STYLES = {
    "academic": "Akademik özet: kavramları, yöntemi, bulguları ve sonuçları ciddi bir akademik dille açıkla.",
    "executive": "Yönetici özeti: karar vericiler için ana sonuçları, etkileri ve önerileri kısa ve net yaz.",
    "bullets": "Madde madde özet: en önemli noktaları okunabilir maddeler halinde ver.",
    "technical": "Teknik özet: teknik terimleri, süreçleri, varsayımları ve sınırlılıkları vurgula.",
    "child": "Çocuklara anlatır gibi özet: basit, anlaşılır ve benzetmeli bir dille açıkla.",
}

AI_SUMMARY_LABELS = {
    "academic": "Akademik özet",
    "executive": "Yönetici özeti",
    "bullets": "Madde madde özet",
    "technical": "Teknik özet",
    "child": "Çocuklara anlatır gibi",
}

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")
DEFAULT_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "20"))


@dataclass
class SourceChunk:
    page: int
    text: str
    score: float = 0.0

    def to_cache(self) -> dict[str, object]:
        return {"page": self.page, "text": self.text}

    @classmethod
    def from_cache(cls, data: dict[str, object], score: float = 0.0) -> "SourceChunk":
        return cls(page=int(data["page"]), text=str(data["text"]), score=score)


def ensure_sync_ai_allowed(document: PdfDocument) -> None:
    if document.page_count > AI_SYNC_MAX_PAGES or len(document.full_text) > AI_SYNC_MAX_CHARS:
        raise RuntimeError(
            "Bu belge senkron AI işlemi için çok büyük. Arka plan görev sistemiyle işlenmesi gerekir."
        )


def openai_status() -> dict[str, str | bool]:
    if not os.getenv("OPENAI_API_KEY"):
        return {"ready": False, "message": "OPENAI_API_KEY tanımlı değil. AI özellikleri için ortam değişkeni ekleyin."}
    try:
        import openai  # noqa: F401
    except ImportError:
        return {"ready": False, "message": "openai paketi yüklü değil. `pip install -r requirements.txt` çalıştırın."}
    return {"ready": True, "message": f"OpenAI hazır: {DEFAULT_MODEL}"}


def client():
    from openai import OpenAI

    return OpenAI(timeout=OPENAI_TIMEOUT, max_retries=0)


def document_chunks(document: PdfDocument, max_chars: int = 1400) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for page, page_text in enumerate(document.text_by_page, start=1):
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", page_text) if part.strip()]
        if not paragraphs and page_text.strip():
            paragraphs = [page_text.strip()]
        buffer = ""
        for paragraph in paragraphs:
            if len(buffer) + len(paragraph) + 2 > max_chars and buffer:
                chunks.append(SourceChunk(page, buffer))
                buffer = paragraph
            else:
                buffer = f"{buffer}\n\n{paragraph}".strip()
        if buffer:
            chunks.append(SourceChunk(page, buffer))
    return chunks


def trim_document_text(document: PdfDocument, max_chars: int = 18000) -> str:
    pieces = []
    total = 0
    for page, text in enumerate(document.text_by_page, start=1):
        piece = f"[Sayfa {page}]\n{text.strip()}"
        if total + len(piece) > max_chars:
            remaining = max_chars - total
            if remaining > 500:
                pieces.append(piece[:remaining])
            break
        pieces.append(piece)
        total += len(piece)
    return "\n\n".join(pieces)


def call_response(prompt: str, instructions: str) -> str:
    response = client().responses.create(
        model=DEFAULT_MODEL,
        instructions=instructions,
        input=prompt,
    )
    return getattr(response, "output_text", "") or "Model yanıtı boş döndü."


def ai_summary(document: PdfDocument, style: str) -> str:
    status = openai_status()
    if not status["ready"]:
        raise RuntimeError(str(status["message"]))
    ensure_sync_ai_allowed(document)
    style_instruction = AI_SUMMARY_STYLES.get(style, AI_SUMMARY_STYLES["executive"])
    prompt = (
        f"{style_instruction}\n\n"
        "Yanıt Türkçe olsun. Önemli iddialarda ilgili sayfa numarasını parantez içinde belirt.\n\n"
        f"Belge metni:\n{trim_document_text(document)}"
    )
    return call_response(
        prompt,
        "Sen PDF belgelerini güvenilir biçimde özetleyen bir analiz asistanısın. Metinde olmayan bilgi ekleme.",
    )


def lexical_score(query: str, text: str) -> float:
    query_terms = set(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{3,}", query.lower()))
    text_terms = set(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{3,}", text.lower()))
    if not query_terms or not text_terms:
        return 0.0
    return len(query_terms & text_terms) / math.sqrt(len(query_terms) * len(text_terms))


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def embedding_search(document: PdfDocument, query: str, chunks: list[SourceChunk], limit: int = 5) -> list[SourceChunk]:
    cache = get_embedding_cache(document.document_id, DEFAULT_EMBEDDING_MODEL) if document.document_id else None
    if cache:
        cached_chunks, chunk_vectors = cache
        chunks = [SourceChunk.from_cache(chunk) for chunk in cached_chunks]
    else:
        response = client().embeddings.create(
            model=DEFAULT_EMBEDDING_MODEL,
            input=[chunk.text for chunk in chunks],
        )
        chunk_vectors = [item.embedding for item in response.data]
        if document.document_id:
            save_embedding_cache(
                document.document_id,
                DEFAULT_EMBEDDING_MODEL,
                [chunk.to_cache() for chunk in chunks],
                chunk_vectors,
            )

    query_response = client().embeddings.create(model=DEFAULT_EMBEDDING_MODEL, input=[query])
    query_vector = query_response.data[0].embedding
    scored = [
        SourceChunk(chunk.page, chunk.text, cosine(query_vector, vector))
        for chunk, vector in zip(chunks, chunk_vectors)
    ]
    return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]


def semantic_search(document: PdfDocument, query: str, limit: int = 5) -> tuple[list[SourceChunk], str]:
    chunks = document_chunks(document)
    if not query.strip() or not chunks:
        return [], ""
    status = openai_status()
    if status["ready"]:
        try:
            ensure_sync_ai_allowed(document)
            return embedding_search(document, query, chunks, limit), "OpenAI embeddings ile semantik arama"
        except Exception as exc:
            fallback = str(exc)
    else:
        fallback = str(status["message"])
    scored = [SourceChunk(chunk.page, chunk.text, lexical_score(query, chunk.text)) for chunk in chunks]
    return sorted(scored, key=lambda item: item.score, reverse=True)[:limit], f"Leksik yedek arama: {fallback}"


def answer_question(document: PdfDocument, question: str) -> str:
    status = openai_status()
    if not status["ready"]:
        raise RuntimeError(str(status["message"]))
    ensure_sync_ai_allowed(document)
    chunks, mode = semantic_search(document, question, limit=6)
    context = "\n\n".join(f"[Sayfa {chunk.page}]\n{chunk.text}" for chunk in chunks)
    prompt = (
        f"Soru: {question}\n\n"
        f"İlgili bağlam ({mode}):\n{context}\n\n"
        "Cevapta kaynak sayfa numaralarını belirt. Kısa alıntılar yap ve belirsiz kalan noktaları açıkça söyle."
    )
    return call_response(
        prompt,
        "Sen PDF üzerinde soru-cevap yapan bir asistansın. Sadece verilen bağlama dayanarak Türkçe cevap ver.",
    )


def suggested_questions(document: PdfDocument) -> list[str]:
    if document.page_count >= 3:
        return ["Bu belge ne anlatıyor?", "3. bölümde ne deniyor?", "Riskler nelerdir?"]
    return ["Bu belge ne anlatıyor?", "Bu belgede öne çıkan noktalar neler?", "Riskler nelerdir?"]
