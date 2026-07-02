from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from .analysis import keywords, summarize
from .config import DB_PATH, SQLITE_JOURNAL_MODE, STORAGE_DIR, SUMMARY_LENGTHS
from .models import PdfDocument


DOCUMENTS: dict[str, PdfDocument] = {}
LEARNING_EVENTS_MEMORY: list[dict[str, object]] = []


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        connection.execute(f"PRAGMA journal_mode={SQLITE_JOURNAL_MODE}")
    except sqlite3.OperationalError:
        connection.execute("PRAGMA journal_mode=MEMORY")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_bytes BLOB NOT NULL DEFAULT X'',
                file_path TEXT NOT NULL DEFAULT '',
                size_bytes INTEGER NOT NULL DEFAULT 0,
                owner_id TEXT NOT NULL DEFAULT 'local',
                text_by_page TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                keywords TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        ensure_column(connection, "documents", "file_path", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "documents", "size_bytes", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(connection, "documents", "owner_id", "TEXT NOT NULL DEFAULT 'local'")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                page INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS embedding_cache (
                document_id TEXT NOT NULL,
                model TEXT NOT NULL,
                chunks_json TEXT NOT NULL,
                vectors_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(document_id, model),
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
            """
        )
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id TEXT NOT NULL DEFAULT 'local',
                    document_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    topic TEXT NOT NULL DEFAULT '',
                    question TEXT NOT NULL DEFAULT '',
                    page INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
                """
            )
        except sqlite3.OperationalError:
            pass
        connection.execute("CREATE INDEX IF NOT EXISTS idx_documents_owner_uploaded ON documents(owner_id, uploaded_at)")
        try:
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_learning_owner_created ON learning_events(owner_id, created_at)"
            )
        except sqlite3.OperationalError:
            pass


def document_file_path(document_id: str, filename: str) -> Path:
    suffix = Path(filename).suffix.lower() or ".pdf"
    return STORAGE_DIR / f"{document_id}{suffix}"


def persist_document_file(document_id: str, document: PdfDocument) -> str:
    path = document_file_path(document_id, document.filename)
    path.write_bytes(document.file_bytes)
    return str(path.relative_to(DB_PATH.parent))


def read_document_file(file_path: str, fallback: bytes | None = None) -> bytes:
    if file_path:
        path = Path(file_path)
        if not path.is_absolute():
            path = DB_PATH.parent / path
        if path.exists():
            return path.read_bytes()
    return fallback or b""


def row_to_document(row: sqlite3.Row) -> PdfDocument:
    file_path = row["file_path"] if "file_path" in row.keys() else ""
    fallback = row["file_bytes"] if "file_bytes" in row.keys() else b""
    file_bytes = read_document_file(file_path, fallback)
    return PdfDocument(
        filename=row["filename"],
        file_bytes=file_bytes,
        text_by_page=json.loads(row["text_by_page"]),
        uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
        document_id=row["id"],
        storage_path=file_path,
        owner_id=row["owner_id"] if "owner_id" in row.keys() else "local",
    )


def load_documents() -> None:
    with db() as connection:
        rows = connection.execute("SELECT * FROM documents ORDER BY uploaded_at").fetchall()
    for row in rows:
        DOCUMENTS[row["id"]] = row_to_document(row)


def save_document(document_id: str, document: PdfDocument, owner_id: str = "local") -> None:
    file_path = persist_document_file(document_id, document)
    document.document_id = document_id
    document.storage_path = file_path
    document.owner_id = owner_id
    with db() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO documents
            (id, filename, file_bytes, file_path, size_bytes, owner_id, text_by_page, uploaded_at, summary, keywords)
            VALUES (?, ?, X'', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                document.filename,
                file_path,
                len(document.file_bytes),
                owner_id,
                json.dumps(document.text_by_page, ensure_ascii=False),
                document.uploaded_at.isoformat(),
                summarize(document.full_text, SUMMARY_LENGTHS["medium"]),
                json.dumps(keywords(document.full_text, 10), ensure_ascii=False),
            ),
        )


def get_document(document_id: str | None, owner_id: str | None = None) -> PdfDocument | None:
    if not document_id:
        return None
    document = DOCUMENTS.get(document_id)
    if document and (owner_id is None or document.owner_id == owner_id):
        return document
    with db() as connection:
        if owner_id is None:
            row = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM documents WHERE id = ? AND owner_id = ?",
                (document_id, owner_id),
            ).fetchone()
    if row is None:
        return None
    document = row_to_document(row)
    DOCUMENTS[document_id] = document
    return document


def recent_documents(limit: int = 8, owner_id: str = "local") -> list[dict[str, object]]:
    with db() as connection:
        rows = connection.execute(
            """
            SELECT id, filename, file_path, file_bytes, size_bytes, text_by_page, uploaded_at, owner_id
            FROM documents
            WHERE owner_id = ?
            ORDER BY uploaded_at DESC
            LIMIT ?
            """,
            (owner_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "page_count": len(json.loads(row["text_by_page"])),
            "size_label": row_to_document(row).size_label,
            "uploaded_at_label": datetime.fromisoformat(row["uploaded_at"]).strftime("%d.%m.%Y %H:%M"),
        }
        for row in rows
    ]


def add_note(document_id: str, page: int, content: str) -> None:
    with db() as connection:
        connection.execute(
            "INSERT INTO notes (document_id, page, content, created_at) VALUES (?, ?, ?, ?)",
            (document_id, page, content, datetime.now().isoformat()),
        )


def log_learning_event(
    owner_id: str,
    document_id: str,
    event_type: str,
    topic: str = "",
    question: str = "",
    page: int | None = None,
) -> None:
    def remember_in_process() -> None:
        created_at = datetime.now().isoformat()
        if event_type == "view":
            today = datetime.now().date().isoformat()
            if any(
                row["owner_id"] == owner_id
                and row["document_id"] == document_id
                and row["event_type"] == "view"
                and str(row["created_at"]).startswith(today)
                for row in LEARNING_EVENTS_MEMORY
            ):
                return
        LEARNING_EVENTS_MEMORY.append(
            {
                "owner_id": owner_id,
                "document_id": document_id,
                "event_type": event_type,
                "topic": topic,
                "question": question,
                "page": page,
                "created_at": created_at,
                "filename": DOCUMENTS.get(document_id).filename if document_id in DOCUMENTS else "Geçici belge",
            }
        )

    with db() as connection:
        try:
            if event_type == "view":
                today = datetime.now().date().isoformat()
                existing = connection.execute(
                    """
                    SELECT id FROM learning_events
                    WHERE owner_id = ? AND document_id = ? AND event_type = 'view' AND created_at LIKE ?
                    LIMIT 1
                    """,
                    (owner_id, document_id, f"{today}%"),
                ).fetchone()
                if existing is not None:
                    return
            connection.execute(
                """
                INSERT INTO learning_events (owner_id, document_id, event_type, topic, question, page, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (owner_id, document_id, event_type, topic, question, page, datetime.now().isoformat()),
            )
        except (sqlite3.IntegrityError, sqlite3.OperationalError):
            remember_in_process()
            return


def learning_memory_summary(owner_id: str = "local", limit: int = 8) -> dict[str, object]:
    try:
        with db() as connection:
            rows = list(
                connection.execute(
                    """
                    SELECT event_type, topic, question, page, created_at, documents.filename
                    FROM learning_events
                    LEFT JOIN documents ON documents.id = learning_events.document_id
                    WHERE learning_events.owner_id = ?
                    ORDER BY learning_events.created_at DESC
                    LIMIT 120
                    """,
                    (owner_id,),
                ).fetchall()
            )
    except sqlite3.OperationalError:
        rows = []
    rows.extend(row for row in LEARNING_EVENTS_MEMORY if row["owner_id"] == owner_id)
    rows = sorted(rows, key=lambda row: str(row["created_at"]), reverse=True)[:120]

    topic_counts: Counter[str] = Counter()
    questions = []
    viewed_docs: dict[str, str] = {}
    for row in rows:
        filename = row["filename"] or "Silinmiş belge"
        event_type = row["event_type"]
        topic = row["topic"]
        question = row["question"]
        created_at = row["created_at"]
        if event_type == "view":
            viewed_docs[filename] = created_at
        if question:
            questions.append(
                {
                    "question": question,
                    "topic": topic,
                    "filename": filename,
                    "page": row["page"],
                    "created_at": datetime.fromisoformat(created_at).strftime("%d.%m %H:%M"),
                }
            )
        if topic:
            topic_counts.update(topic.strip() for topic in topic.split(",") if topic.strip())

    weak_topics = [topic for topic, _ in topic_counts.most_common(6)]
    review_plan = [
        {
            "title": "Soru geçmişini kapat",
            "detail": "Son sorduğun soruları tekrar cevapla ve cevabı kanıt kartlarından doğrula.",
        }
    ]
    review_plan.extend(
        {
            "title": f"{topic} konusunu pekiştir",
            "detail": "Bu kavram için flashcard, boşluk doldurma ve ilgili PDF sayfasını birlikte gözden geçir.",
        }
        for topic in weak_topics[:3]
    )
    if not weak_topics:
        review_plan.append(
            {
                "title": "İlk öğrenme izini oluştur",
                "detail": "Bir PDF açıp belgeyle ilgili 2-3 soru sor; StudyMate tekrar planını buna göre kişiselleştirir.",
            }
        )

    return {
        "read_document_count": len(viewed_docs),
        "question_count": len(questions),
        "weak_topics": weak_topics,
        "recent_questions": questions[:limit],
        "review_plan": review_plan[:4],
    }


def note_rows(document_id: str, page: int | None = None) -> list[sqlite3.Row]:
    query = "SELECT * FROM notes WHERE document_id = ?"
    params: list[object] = [document_id]
    if page is not None:
        query += " AND page = ?"
        params.append(page)
    query += " ORDER BY created_at DESC"
    with db() as connection:
        return connection.execute(query, params).fetchall()


def get_embedding_cache(document_id: str, model: str) -> tuple[list[dict[str, object]], list[list[float]]] | None:
    with db() as connection:
        row = connection.execute(
            "SELECT chunks_json, vectors_json FROM embedding_cache WHERE document_id = ? AND model = ?",
            (document_id, model),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["chunks_json"]), json.loads(row["vectors_json"])


def save_embedding_cache(
    document_id: str,
    model: str,
    chunks: list[dict[str, object]],
    vectors: list[list[float]],
) -> None:
    with db() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO embedding_cache (document_id, model, chunks_json, vectors_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                document_id,
                model,
                json.dumps(chunks, ensure_ascii=False),
                json.dumps(vectors),
                datetime.now().isoformat(),
            ),
        )
