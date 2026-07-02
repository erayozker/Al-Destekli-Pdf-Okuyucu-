from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PdfDocument:
    filename: str
    file_bytes: bytes
    text_by_page: list[str]
    uploaded_at: datetime
    document_id: str = ""
    storage_path: str = ""
    owner_id: str = "local"

    @property
    def page_count(self) -> int:
        return len(self.text_by_page)

    @property
    def full_text(self) -> str:
        return "\n\n".join(self.text_by_page).strip()

    @property
    def word_count(self) -> int:
        return len(re.findall(r"\b\w+\b", self.full_text, flags=re.UNICODE))

    @property
    def size_label(self) -> str:
        size = len(self.file_bytes)
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    @property
    def uploaded_at_label(self) -> str:
        return self.uploaded_at.strftime("%d.%m.%Y %H:%M")
