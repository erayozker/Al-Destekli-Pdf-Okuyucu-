from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import Response, flash, redirect, request, session, url_for
from werkzeug.security import check_password_hash

from .config import ADMIN_PASSWORD, ADMIN_PASSWORD_HASH, ADMIN_USERNAME, AUTH_REQUIRED


F = TypeVar("F", bound=Callable[..., object])


def current_user_id() -> str:
    if not AUTH_REQUIRED:
        return "local"
    return str(session.get("user_id") or "")


def is_authenticated() -> bool:
    return not AUTH_REQUIRED or bool(session.get("user_id"))


def verify_login(username: str, password: str) -> bool:
    if username != ADMIN_USERNAME:
        return False
    if ADMIN_PASSWORD_HASH:
        return check_password_hash(ADMIN_PASSWORD_HASH, password)
    return bool(ADMIN_PASSWORD) and password == ADMIN_PASSWORD


def login_user() -> None:
    session.clear()
    session["user_id"] = ADMIN_USERNAME


def logout_user() -> None:
    session.clear()


def login_required(view: F) -> F:
    @wraps(view)
    def wrapped(*args: object, **kwargs: object) -> object:
        if is_authenticated():
            return view(*args, **kwargs)
        flash("Devam etmek için giriş yapın.", "error")
        return redirect(url_for("main.login", next=request.full_path))

    return wrapped  # type: ignore[return-value]


def require_owner(document_id: str):
    from .repository import get_document

    document = get_document(document_id, current_user_id())
    if document is None:
        flash("Belge bulunamadı veya bu belgeye erişim yetkiniz yok.", "error")
        return None
    return document
