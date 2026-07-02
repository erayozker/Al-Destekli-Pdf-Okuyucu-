from __future__ import annotations

import csv
import io
import secrets
from datetime import datetime

from flask import Blueprint, Response, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from .analysis import comparison_result, keywords, page_summaries, section_summaries, summarize
from .auth import current_user_id, is_authenticated, login_user, logout_user, verify_login
from .ai_service import (
    AI_SUMMARY_LABELS,
    ai_summary,
    answer_question,
    openai_status,
    semantic_search,
    suggested_questions,
)
from .config import AUTH_REQUIRED, ENABLE_OCR, MAX_PDF_BYTES, PDF_MAGIC, SUMMARY_LABELS, SUMMARY_LENGTHS, VIRUS_SCAN_ENABLED
from .evidence import build_evidence_cards, question_terms
from .options import current_options, option_args, parse_float, parse_int
from .pdf_service import extract_image, extract_tables, list_images, read_pdf, render_page
from .repository import (
    DOCUMENTS,
    add_note as save_note,
    get_document,
    learning_memory_summary,
    log_learning_event,
    note_rows,
    recent_documents,
    save_document,
)
from .search import highlight_terms, search_document, search_terms
from .study import build_study_mode


bp = Blueprint("main", __name__)


@bp.before_request
def require_login() -> Response | None:
    if not AUTH_REQUIRED or is_authenticated():
        return None
    if request.endpoint in {"main.login", "main.login_post", "static"}:
        return None
    return redirect(url_for("main.login", next=request.full_path))


@bp.get("/login")
def login() -> str:
    return render_template("login.html")


@bp.post("/login")
def login_post() -> Response:
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    if verify_login(username, password):
        login_user()
        flash("Giriş başarılı.", "success")
        return redirect(request.args.get("next") or url_for("main.index"))
    flash("Kullanıcı adı veya parola hatalı.", "error")
    return redirect(url_for("main.login"))


@bp.post("/logout")
def logout() -> Response:
    logout_user()
    flash("Oturum kapatıldı.", "success")
    return redirect(url_for("main.login" if AUTH_REQUIRED else "main.index"))


def validate_pdf_upload(filename: str, file_bytes: bytes) -> str | None:
    if not filename.lower().endswith(".pdf"):
        return "Sadece PDF dosyaları desteklenir."
    if len(file_bytes) > MAX_PDF_BYTES:
        return f"PDF dosyası çok büyük. En fazla {MAX_PDF_BYTES // (1024 * 1024)} MB yükleyin."
    if not file_bytes.startswith(PDF_MAGIC):
        return "Dosya PDF imzası taşımıyor. Lütfen geçerli bir PDF yükleyin."
    if VIRUS_SCAN_ENABLED:
        return "Virüs tarama servisi yapılandırılmadığı için yükleme reddedildi."
    return None


def get_document_or_redirect(document_id: str):
    document = get_document(document_id, current_user_id())
    if document is None:
        flash("Belge bulunamadı veya bu belgeye erişim yetkiniz yok.", "error")
    return document


def render_home(document=None, document_id: str | None = None) -> str:
    options = current_options(request)
    compare_left = request.args.get("compare_left", "")
    compare_right = request.args.get("compare_right", "")
    compare = None

    if compare_left and compare_right:
        left_document = get_document(compare_left, current_user_id())
        right_document = get_document(compare_right, current_user_id())
        if left_document and right_document:
            compare = comparison_result(left_document, right_document, int(options["keyword_limit"]))

    common_context = {
        "recent_documents": recent_documents(owner_id=current_user_id()),
        "history_documents": recent_documents(30, owner_id=current_user_id()),
        "summary_options": SUMMARY_LABELS,
        "compare": compare,
        "compare_left": compare_left,
        "compare_right": compare_right,
        "auth_required": AUTH_REQUIRED,
        "current_user": current_user_id(),
        **options,
    }

    if document is None:
        return render_template(
            "index.html",
            document=None,
            learning_memory=learning_memory_summary(current_user_id()),
            **common_context,
        )

    page = parse_int(request.args.get("page"), 1, 1, max(document.page_count, 1))
    log_learning_event(current_user_id(), str(document_id), "view", page=page)
    page_text = document.text_by_page[page - 1] if document.text_by_page else ""
    terms = search_terms(str(options["query"]), str(options["search_mode"]))
    summary = summarize(document.full_text, SUMMARY_LENGTHS[str(options["summary_length"])])
    selected_summary = summarize(str(options["selected_text"]), 3) if options["selected_text"] else ""
    search_results = search_document(document, options)
    ai_style = request.args.get("ai_style", "")
    ai_result = ""
    ai_error = ""
    question = request.args.get("question", "").strip()
    qa_answer = ""
    evidence_cards = []
    evidence_mode = ""
    semantic_query = request.args.get("semantic_q", "").strip()
    semantic_results = []
    semantic_mode = ""

    if ai_style:
        try:
            ai_result = ai_summary(document, ai_style)
        except Exception as exc:
            ai_error = f"AI özet alınamadı: {exc}"

    if question:
        question_topic = ", ".join(question_terms(question)[:4])
        try:
            qa_answer = answer_question(document, question)
        except Exception as exc:
            ai_error = f"Soru-cevap yanıtı alınamadı: {exc}"
        evidence_results, evidence_mode = semantic_search(document, question, limit=4)
        evidence_cards = build_evidence_cards(document, question, evidence_results)
        log_learning_event(current_user_id(), str(document_id), "question", question_topic, question, page)

    if semantic_query:
        semantic_results, semantic_mode = semantic_search(document, semantic_query)
        semantic_topic = ", ".join(question_terms(semantic_query)[:4])
        log_learning_event(current_user_id(), str(document_id), "semantic_search", semantic_topic, semantic_query, page)

    study_mode = build_study_mode(document, int(options["keyword_limit"]))

    return render_template(
        "index.html",
        document=document,
        document_id=document_id,
        page=page,
        page_text=page_text,
        highlighted_page_text=highlight_terms(
            page_text,
            terms,
            bool(options["case_sensitive"]),
            bool(options["whole_word"]),
        ),
        summary=summary,
        page_summary=summarize(page_text, 3),
        selected_summary=selected_summary,
        key_terms=keywords(document.full_text, int(options["keyword_limit"])),
        search_results=search_results,
        total_matches=sum(int(result["count"]) for result in search_results),
        base_args=option_args(options),
        page_summaries=page_summaries(document),
        section_summaries=section_summaries(document),
        tables=extract_tables(document, page),
        images=list_images(document),
        notes=note_rows(str(document_id), page),
        all_notes=note_rows(str(document_id)),
        ai_summary_labels=AI_SUMMARY_LABELS,
        ai_style=ai_style,
        ai_result=ai_result,
        ai_error=ai_error,
        openai_status=openai_status(),
        question=question,
        qa_answer=qa_answer,
        evidence_cards=evidence_cards,
        evidence_mode=evidence_mode,
        suggested_questions=suggested_questions(document),
        study_mode=study_mode,
        learning_memory=learning_memory_summary(current_user_id()),
        semantic_query=semantic_query,
        semantic_results=semantic_results,
        semantic_mode=semantic_mode,
        **common_context,
    )


@bp.get("/")
def index() -> str:
    document_id = request.args.get("doc")
    document = get_document(document_id, current_user_id())
    return render_home(document, document_id) if document else render_home()


@bp.post("/upload")
def upload() -> Response:
    uploaded_file = request.files.get("pdf")
    if uploaded_file is None or uploaded_file.filename == "":
        flash("Lütfen bir PDF dosyası seçin.", "error")
        return redirect(url_for("main.index"))

    filename = secure_filename(uploaded_file.filename)
    file_bytes = uploaded_file.read()
    validation_error = validate_pdf_upload(filename, file_bytes)
    if validation_error:
        flash(validation_error, "error")
        return redirect(url_for("main.index"))

    try:
        document = read_pdf(filename, file_bytes)
    except Exception:
        flash("PDF okunamadı. Dosya bozuk veya şifreli olabilir.", "error")
        return redirect(url_for("main.index"))

    if not document.full_text and not ENABLE_OCR:
        flash("PDF metin içermiyor olabilir. Taranmış belgeler için OCR desteğini etkinleştirin.", "error")

    document_id = secrets.token_urlsafe(12)
    DOCUMENTS[document_id] = document
    save_document(document_id, document, current_user_id())
    flash(f"{filename} başarıyla yüklendi ve analiz edildi.", "success")
    return redirect(url_for("main.index", doc=document_id))


@bp.post("/notes/<document_id>")
def add_note(document_id: str) -> Response:
    document = get_document_or_redirect(document_id)
    if document is None:
        return redirect(url_for("main.index"))
    page = parse_int(request.form.get("page"), 1, 1, max(document.page_count, 1))
    content = (request.form.get("content") or "").strip()
    if content:
        save_note(document_id, page, content)
        flash("Not kaydedildi.", "success")
    else:
        flash("Boş not kaydedilmedi.", "error")
    return redirect(url_for("main.index", doc=document_id, page=page))


@bp.post("/compare-upload")
def compare_upload() -> Response:
    files = [request.files.get("left_pdf"), request.files.get("right_pdf")]
    ids: list[str] = []
    for uploaded_file in files:
        if uploaded_file is None or uploaded_file.filename == "":
            flash("Karşılaştırma için iki PDF seçin.", "error")
            return redirect(url_for("main.index"))
        filename = secure_filename(uploaded_file.filename)
        file_bytes = uploaded_file.read()
        validation_error = validate_pdf_upload(filename, file_bytes)
        if validation_error:
            flash(validation_error, "error")
            return redirect(url_for("main.index"))
        try:
            document = read_pdf(filename, file_bytes)
        except Exception:
            flash(f"{filename} okunamadı.", "error")
            return redirect(url_for("main.index"))
        document_id = secrets.token_urlsafe(12)
        DOCUMENTS[document_id] = document
        save_document(document_id, document, current_user_id())
        ids.append(document_id)
    return redirect(url_for("main.index", compare_left=ids[0], compare_right=ids[1]))


@bp.get("/page/<document_id>/<int:page_number>.png")
def page_image(document_id: str, page_number: int) -> Response:
    document = get_document_or_redirect(document_id)
    if document is None:
        return redirect(url_for("main.index"))
    page_number = min(max(page_number, 1), document.page_count)
    zoom = parse_float(request.args.get("zoom"), 1.6, 0.2, 3.0)
    return Response(render_page(document, page_number, zoom), mimetype="image/png")


@bp.get("/image/<document_id>/<int:xref>")
def download_image(document_id: str, xref: int) -> Response:
    document = get_document_or_redirect(document_id)
    if document is None:
        return redirect(url_for("main.index"))
    try:
        info = extract_image(document, xref)
    except Exception:
        flash("Görsel çıkarılamadı.", "error")
        return redirect(url_for("main.index", doc=document_id))
    ext = info.get("ext", "bin")
    return send_file(
        io.BytesIO(info.get("image", b"")),
        as_attachment=True,
        download_name=f"{document.filename.rsplit('.', 1)[0]}-gorsel-{xref}.{ext}",
    )


@bp.get("/download/<document_id>/<kind>")
def download(document_id: str, kind: str) -> Response:
    document = get_document_or_redirect(document_id)
    if document is None:
        return redirect(url_for("main.index"))

    stem = document.filename.rsplit(".", 1)[0]
    if kind == "summary":
        summary_length = request.args.get("summary", "medium")
        if summary_length not in SUMMARY_LENGTHS:
            summary_length = "medium"
        data = summarize(document.full_text, SUMMARY_LENGTHS[summary_length]).encode("utf-8")
        filename = f"{stem}-ozet.txt"
        mimetype = "text/plain; charset=utf-8"
    elif kind == "notes":
        content = "\n\n".join(
            f"Sayfa {row['page']} - {datetime.fromisoformat(row['created_at']).strftime('%d.%m.%Y %H:%M')}\n{row['content']}"
            for row in note_rows(document_id)
        )
        data = content.encode("utf-8")
        filename = f"{stem}-notlar.txt"
        mimetype = "text/plain; charset=utf-8"
    elif kind == "tables":
        output = io.StringIO()
        writer = csv.writer(output)
        for table in extract_tables(document):
            writer.writerow([f"Sayfa {table['page']} Tablo {table['index']}"])
            writer.writerows(table["rows"])
            writer.writerow([])
        data = output.getvalue().encode("utf-8-sig")
        filename = f"{stem}-tablolar.csv"
        mimetype = "text/csv; charset=utf-8"
    else:
        data = document.full_text.encode("utf-8")
        filename = f"{stem}-tam-metin.txt"
        mimetype = "text/plain; charset=utf-8"

    return send_file(io.BytesIO(data), as_attachment=True, download_name=filename, mimetype=mimetype)
