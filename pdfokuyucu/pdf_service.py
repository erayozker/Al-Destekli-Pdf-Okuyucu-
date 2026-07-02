from __future__ import annotations

from datetime import datetime

import fitz

from .models import PdfDocument


def read_pdf(filename: str, file_bytes: bytes) -> PdfDocument:
    with fitz.open(stream=file_bytes, filetype="pdf") as document:
        text_by_page = [page.get_text("text").strip() for page in document]
    return PdfDocument(filename, file_bytes, text_by_page, datetime.now())


def render_page(document: PdfDocument, page_number: int, zoom: float = 1.6) -> bytes:
    with fitz.open(stream=document.file_bytes, filetype="pdf") as pdf:
        page = pdf.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pixmap.tobytes("png")


def extract_tables(document: PdfDocument, page_number: int | None = None) -> list[dict[str, object]]:
    tables: list[dict[str, object]] = []
    with fitz.open(stream=document.file_bytes, filetype="pdf") as pdf:
        pages = [page_number - 1] if page_number else range(pdf.page_count)
        for page_index in pages:
            page = pdf.load_page(page_index)
            finder = getattr(page, "find_tables", None)
            if finder is None:
                continue
            try:
                found = finder()
            except Exception:
                continue
            for table_index, table in enumerate(found.tables, start=1):
                rows = table.extract()
                if rows:
                    tables.append({"page": page_index + 1, "index": table_index, "rows": rows})
    return tables


def list_images(document: PdfDocument) -> list[dict[str, object]]:
    images: list[dict[str, object]] = []
    seen: set[int] = set()
    with fitz.open(stream=document.file_bytes, filetype="pdf") as pdf:
        for page_index in range(pdf.page_count):
            for image_index, image in enumerate(pdf.load_page(page_index).get_images(full=True), start=1):
                xref = int(image[0])
                if xref in seen:
                    continue
                seen.add(xref)
                info = pdf.extract_image(xref)
                images.append(
                    {
                        "page": page_index + 1,
                        "index": image_index,
                        "xref": xref,
                        "ext": info.get("ext", "bin"),
                        "size": len(info.get("image", b"")),
                    }
                )
    return images


def extract_image(document: PdfDocument, xref: int) -> dict[str, object]:
    with fitz.open(stream=document.file_bytes, filetype="pdf") as pdf:
        return pdf.extract_image(xref)
